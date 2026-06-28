"""
Universal Hardware Monitor Server
==================================
Provides GPU/Hardware stats via:
  1. REST API (primary) -- GET /btx/hw/stats returns JSON
  2. WebSocket (fallback) -- /btx/ws/hw_monitor for streaming

IMPORTANT: All hardware queries run in a background daemon thread.
The REST/WS handlers read from a thread-safe cache, returning
instantly without blocking. While the backend initializes (first
few seconds), a loading placeholder JSON is served.

JSON SAFETY: The initial cache MUST contain ALL keys that the
frontend JS expects, including 'is_apu', 'is_loading', etc.
vram_total_mb is set to 1 (not 0) to prevent division-by-zero
in the frontend progress bar calculations.

Thread-safety contract:
  - `self._cache` (dict) is mutated only inside `_cache_lock`.
  - `self.history` / `self._util_history` (deque) are mutated only inside
    `_history_lock`. Reading them via `list(...)` outside the lock is a
    data race per CPython semantics (list() walks internal pointers while
    another thread mutates).
  - `_stop_event` signals the update loop to exit on `close()`.
"""

import atexit
import asyncio
import json
import logging
import threading
import time
from collections import deque

# GPU Utilization smoothing — window size for Peak Hold / Moving Average
# Prevents sudden drops to 0% caused by PDH engine switching or micro-stutters.
_UTIL_SMOOTH_WINDOW = 4

# Poll interval (seconds) between background updates.
_POLL_INTERVAL_SECONDS = 0.5
# Exponential backoff after consecutive fetch errors — bounds CPU spam if
# the backend stays broken. See _update_loop() for the exact schedule.
_POLL_BACKOFF_MAX_SECONDS = 2.0
# TTL (seconds) for the cached `_read_temp()` fallback result. Without this,
# every poll that sees temp=0 OR fan=0 would spawn PowerShell / wmic
# (Windows-only fallback), wasting CPU on Linux. The cache is bypassed when
# the fallback returns real data.
_TEMP_FAN_CACHE_SECONDS = 5.0

logger = logging.getLogger(__name__)


class HardwareMonitorServer:
    """Thread-safe singleton providing GPU sensor data via background cache.

    Architecture:
      - A daemon thread runs _update_loop() which polls the hardware
        backend every 0.5s and writes results to self._cache.
      - get_stats_json() simply reads self._cache (instant, non-blocking).
      - While _update_loop hasn't started yet (backend initializing),
        a safe loading placeholder with ALL expected keys is returned.
      - close() signals the loop to exit (idempotent, safe to call multiple
        times) — used by ComfyUI hot-reload and atexit cleanup.
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        # Double-checked locking for singleton creation.
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._initialized = False
                    cls._instance = inst
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self.monitor = None
        self.history = deque(maxlen=60)
        self._util_history = deque(maxlen=_UTIL_SMOOTH_WINDOW)  # For GPU % smoothing

        # ---- Cache for non-blocking reads ----
        # WARNING: Must contain ALL keys that hw_monitor.js expects.
        # vram_total_mb=1 prevents division-by-zero in frontend bar.
        self._cache = {
            "type": "hw_stats",
            "gpu_id": 0,
            "gpu_name": "Detecting Hardware...",
            "gpu_count": 0,
            "vendor": "unknown",
            "os_type": "unknown",
            "is_available": False,
            "is_loading": True,
            "is_apu": False,
            "error": "Hardware detection in progress",
            "driver": "",
            "history": [],
            "gpu_utilization": 0.0,
            "vram_usage_pct": 0.0,
            "vram_used_mb": 0,
            "vram_total_mb": 1,          # Safe non-zero to prevent JS div/0
            "vram_shared_mb": 0,
            "temperature": 0.0,
            "fan_speed": 0,
            "core_clock_mhz": 0,
            "power_draw_watts": 0.0,
            "backend": "loading",
        }
        self._cache_lock = threading.Lock()
        # Separate lock for the two deques. Cheap because contention is
        # essentially nonexistent (1 writer, 1 reader), but required for
        # CPython's list() snapshot semantics.
        self._history_lock = threading.Lock()
        self._backend_ready = False

        # Shutdown coordination
        self._stop_event = threading.Event()

        # TTL cache for _read_temp() fallback (spares PowerShell on hot path)
        self._temp_cache_value: tuple = (0.0, 0)
        self._temp_cache_timestamp: float = 0.0

        # Start background update thread immediately
        self._update_thread = threading.Thread(
            target=self._update_loop,
            name="BangtrixToolkit-HWMonitor",
            daemon=True,
        )
        try:
            self._update_thread.start()
        except RuntimeError as e:
            logger.error(f"HW Server: failed to start update thread: {e}")
            # Reset init so a retry can be attempted by the caller.
            self._initialized = False
            raise

        # Register atexit cleanup so ComfyUI hot-reload (which keeps the
        # process alive) doesn't leak threads across reloads.
        atexit.register(self.close)

    def close(self) -> None:
        """Signal the background loop to exit. Idempotent and safe to call
        multiple times. Joins the daemon thread with a short timeout so we
        don't hang at interpreter shutdown.
        """
        if not getattr(self, '_initialized', False):
            return
        self._stop_event.set()
        thread = getattr(self, '_update_thread', None)
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
            if thread.is_alive():
                # Daemon thread will die with the process anyway; log so
                # the user can investigate stuck backend.
                logger.debug("HW Server: update thread did not exit in 1s; relying on daemon cleanup")
        # Close the underlying backend so NVML / PDH handles are released.
        monitor = getattr(self, 'monitor', None)
        if monitor is not None:
            try:
                monitor.close()
            except Exception as e:
                logger.debug(f"HW Server: monitor.close() error: {e}")

    def _update_loop(self):
        """Background loop: waits for backend to become ready, then polls
        hardware every 0.5 seconds and caches the result. Backs off on
        repeated errors so a broken backend can't pin a CPU at 2Hz forever.
        """
        # Import here to avoid circular imports at module level
        from monitor import get_universal_monitor

        # Wait for the monitor to be created and finish init
        self.monitor = get_universal_monitor()

        # Wait for background initialization (non-blocking overall since
        # this runs in its own daemon thread)
        ready = self.monitor.wait_ready(timeout=30.0)

        if not ready:
            logger.warning("HW Server: backend not ready after 30s, serving limited stats")
            with self._cache_lock:
                self._cache["is_loading"] = False
                self._cache["is_available"] = False
                self._cache["error"] = "Hardware detection timed out after 30s"
                self._cache["backend"] = "timeout"
            return

        self._backend_ready = True
        logger.info("HW Server: backend ready, starting sensor update loop")

        # Main polling loop — exits on close() signal.
        consecutive_errors = 0
        while not self._stop_event.is_set():
            try:
                data = self._fetch_stats()
                with self._cache_lock:
                    self._cache = data
                consecutive_errors = 0  # reset on success
            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    f"HW Server: update error "
                    f"(#{consecutive_errors}): {e}"
                )

            # Adaptive sleep — fast when healthy, slow after errors. The
            # stop_event.wait() also doubles as the sleep so close() can
            # interrupt immediately instead of waiting for the next tick.
            if consecutive_errors == 0:
                self._stop_event.wait(_POLL_INTERVAL_SECONDS)
            else:
                # 0.5s, 1.0s, 1.5s, 2.0s (capped). Resets to 0.5s on next success.
                backoff = min(_POLL_BACKOFF_MAX_SECONDS,
                              _POLL_INTERVAL_SECONDS * consecutive_errors)
                self._stop_event.wait(backoff)

    def _fetch_stats(self) -> dict:
        """Fetch stats from backend. Runs inside _update_loop (daemon thread)."""
        try:
            monitor = self.monitor
            if not monitor or not monitor.available:
                return {
                    "type": "hw_stats",
                    "gpu_id": 0,
                    "gpu_name": "",
                    "gpu_count": int(monitor.gpu_count) if monitor else 0,
                    "vendor": str(monitor.vendor) if monitor else "unknown",
                    "os_type": str(monitor.os_type) if monitor else "unknown",
                    "is_available": False,
                    "is_loading": False,
                    "is_apu": bool(monitor.has_apu) if monitor else False,
                    "error": "Hardware backend not available",
                    "driver": str(monitor.driver) if monitor else "",
                    "history": self._snapshot_history(),
                    "gpu_utilization": 0.0,
                    "vram_usage_pct": 0.0,
                    "vram_used_mb": 0,
                    "vram_total_mb": 1,
                    "vram_shared_mb": 0,
                    "temperature": 0.0,
                    "fan_speed": 0,
                    "core_clock_mhz": 0,
                    "power_draw_watts": 0.0,
                    "backend": "unavailable",
                }

            stats = monitor.get_gpu_stats(0)
            raw_util = round(float(stats.utilization_gpu or 0), 1)

            # Both deques are written under the history lock. max() is
            # computed inside the lock to avoid a torn read.
            with self._history_lock:
                self.history.append(raw_util)
                self._util_history.append(raw_util)
                util = max(self._util_history)  # Peak Hold
            if util < 0.5 and raw_util > 0:
                # Rare edge case — keep the raw value if it's rising
                util = raw_util
            util = round(util, 1)

            temp = round(float(stats.temperature or 0), 1)
            fan = int(stats.fan_speed or 0)

            # If backend returned 0 temp/fan, try the cross-platform
            # AMD temp reader as a fallback (Windows-only in practice).
            # Result is cached so we don't spawn PowerShell every 0.5s.
            if temp == 0 or fan == 0:
                at, af = self._read_temp_cached()
                if temp == 0 and at > 0:
                    temp = round(float(at), 1)
                if fan == 0 and af > 0:
                    fan = int(af)

            vram_total_mb = int(round(stats.memory_total / (1024 * 1024), 0)) if stats.memory_total > 0 else 1
            vram_used_mb = int(round(stats.memory_used / (1024 * 1024), 0)) if stats.memory_used > 0 else 0

            return {
                "type": "hw_stats",
                "gpu_id": int(stats.gpu_id),
                "gpu_name": str(stats.gpu_name or f"GPU 0"),
                "gpu_count": int(monitor.gpu_count),
                "vendor": str(stats.vendor or monitor.vendor),
                "os_type": str(monitor.os_type),
                "driver": str(stats.driver or monitor.driver or "unknown"),
                "is_apu": bool(stats.is_apu),
                "is_available": bool(stats.is_available),
                "is_loading": False,
                "gpu_utilization": util,
                "vram_usage_pct": round(float(stats.safe_memory_pct() or 0), 1),
                "vram_used_mb": vram_used_mb,
                "vram_total_mb": vram_total_mb,
                "vram_shared_mb": int(round(stats.memory_shared / (1024 * 1024), 0)) if stats.memory_shared > 0 else 0,
                "temperature": temp,
                "fan_speed": fan,
                "core_clock_mhz": int(stats.core_clock or 0),
                "power_draw_watts": round(float(stats.power_draw or 0), 1),
                "history": self._snapshot_history(),
                "backend": str(monitor.driver or "unknown"),
            }
        except Exception as e:
            logger.error(f"HW Server: _fetch_stats error: {e}")
            return {
                "type": "hw_stats",
                "gpu_id": 0,
                "is_available": False,
                "is_loading": False,
                "is_apu": False,
                "error": str(e),
                "history": self._snapshot_history(),
                "gpu_utilization": 0.0,
                "vram_usage_pct": 0.0,
                "vram_used_mb": 0,
                "vram_total_mb": 1,
                "vram_shared_mb": 0,
                "temperature": 0.0,
                "fan_speed": 0,
                "core_clock_mhz": 0,
                "power_draw_watts": 0.0,
                "backend": "error",
            }

    def _snapshot_history(self) -> list:
        """Return a thread-safe snapshot of self.history."""
        with self._history_lock:
            return list(self.history)

    def _read_temp_cached(self) -> tuple:
        """Cached wrapper around amd_temp.read_amd_temperature().

        Result is cached for ``_TEMP_CACHE_SECONDS`` so we don't spawn a
        PowerShell / wmic subprocess every poll (0.5s) when temp or fan
        remains 0. On Linux the underlying reader returns (0.0, 0) instantly,
        but on Windows it can cost 100ms+ per call — caching protects the
        update loop from being dominated by it.
        """
        now = time.time()
        if now - self._temp_cache_timestamp < _TEMP_FAN_CACHE_SECONDS:
            return self._temp_cache_value
        try:
            from monitor.backends.amd_temp import read_amd_temperature
            result = read_amd_temperature()
        except (ImportError, OSError) as e:
            logger.debug(f"HW Server: amd_temp import/read failed: {e}")
            result = (0.0, 0)
        except Exception as e:
            # Defensive — never let the fallback crash the update loop.
            logger.debug(f"HW Server: amd_temp unexpected error: {e}")
            result = (0.0, 0)
        self._temp_cache_value = result
        self._temp_cache_timestamp = now
        return result

    def get_stats_json(self, gpu_id: int = 0) -> dict:
        """Get GPU stats as a JSON-safe dict. Instant — reads from cache.

        This method is called from the main async HTTP handler and must
        NOT block. It simply returns whatever is in the cache right now.
        """
        with self._cache_lock:
            # Return a copy to avoid mutation by caller
            data = dict(self._cache)
            data["gpu_id"] = int(gpu_id)
            return data


def get_hw_server() -> HardwareMonitorServer:
    """Get singleton instance."""
    return HardwareMonitorServer()
