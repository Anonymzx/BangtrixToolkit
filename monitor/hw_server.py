"""
Universal Hardware Monitor Server
==================================
Provides GPU/Hardware stats via:
  1. REST API (primary) -- GET /bangtrix/hw/stats returns JSON
  2. WebSocket (fallback) -- /ws/hw_monitor for streaming

IMPORTANT: All hardware queries run in a background daemon thread.
The REST/WS handlers read from a thread-safe cache, returning
instantly without blocking. While the backend initializes (first
few seconds), a loading placeholder JSON is served.

JSON SAFETY: The initial cache MUST contain ALL keys that the
frontend JS expects, including 'is_apu', 'is_loading', etc.
vram_total_mb is set to 1 (not 0) to prevent division-by-zero
in the frontend progress bar calculations.
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque

logger = logging.getLogger(__name__)


class HardwareMonitorServer:
    """Thread-safe singleton providing GPU sensor data via background cache.

    Architecture:
      - A daemon thread runs _update_loop() which polls the hardware
        backend every 1 second and writes results to self._cache.
      - get_stats_json() simply reads self._cache (instant, non-blocking).
      - While _update_loop hasn't started yet (backend initializing),
        a safe loading placeholder with ALL expected keys is returned.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self.monitor = None
        self.history = deque(maxlen=60)
        self.running = False
        self._task = None

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
        self._backend_ready = False

        # Start background update thread immediately
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

    def _update_loop(self):
        """Background loop: waits for backend to become ready, then polls
        hardware every 1 second and caches the result.
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

        # Main polling loop
        while True:
            try:
                data = self._fetch_stats()
                with self._cache_lock:
                    self._cache = data
            except Exception as e:
                logger.error(f"HW Server: update error: {e}")
            time.sleep(1.0)

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
                    "history": list(self.history),
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
            util = round(float(stats.utilization_gpu or 0), 1)
            self.history.append(util)

            temp = round(float(stats.temperature or 0), 1)
            fan = int(stats.fan_speed or 0)

            # If PDH returned 0 temp, try AMD temp reader
            if temp == 0 or fan == 0:
                try:
                    at, af = self._read_temp()
                    if temp == 0 and at > 0:
                        temp = round(float(at), 1)
                    if fan == 0 and af > 0:
                        fan = int(af)
                except Exception:
                    pass

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
                "history": list(self.history),
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
                "history": list(self.history),
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

    def _read_temp(self) -> tuple:
        """Try to read temperature from AMD temp reader as fallback."""
        try:
            from monitor.backends.amd_temp import read_amd_temperature
            return read_amd_temperature()
        except Exception:
            return 0.0, 0

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