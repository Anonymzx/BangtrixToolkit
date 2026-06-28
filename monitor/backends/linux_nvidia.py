"""
Linux NVIDIA GPU Backend
========================
Reads GPU stats from nvidia-smi on Linux.
Gracefully handles missing nvidia-smi or NVIDIA drivers.

Falls back to 0/N/A values if nvidia-smi fails or times out.
All subprocess calls have timeouts to prevent blocking.

Performance notes:
  - ``nvidia-smi`` is a separate process. Calling it once per poll
    (0.5s) means 2 subprocess invocations / second / GPU — measurable
    on busy systems. We cache the parsed output for ``_SMI_CACHE_TTL``
    seconds; multiple get_stats() calls within that window reuse the
    cached dict instead of spawning a new process.
  - ``pynvml`` (when installed) is initialized once in ``initialize()``
    and shut down in ``close()``. Per-call ``nvmlInit``/``nvmlShutdown``
    would race between REST + WS handlers.
"""

import logging
import subprocess
import threading
import time
from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)

# TTL (seconds) for the per-GPU nvidia-smi result cache. The background
# update loop in hw_server.py polls every 0.5s; this cache makes
# back-to-back get_stats() calls from REST + WS reuse one subprocess
# invocation instead of spawning two.
_SMI_CACHE_TTL = 0.5


class LinuxNVIDIABackend(MonitorBackend):
    """NVIDIA GPU monitoring on Linux via nvidia-smi"""
    name = "linux-nvidia-smi"

    def __init__(self):
        super().__init__()
        self.vendor = "nvidia"
        self._gpu_count = 0
        self._gpu_info: list[dict] = []
        self._initialized = False

        # Per-GPU nvidia-smi result cache, keyed by gpu_id. ``_smi_cache_ts``
        # is the timestamp of the last successful fetch; readers reuse
        # the cache if ``now - ts < _SMI_CACHE_TTL``.
        self._smi_cache: dict[int, HardwareStats] = {}
        self._smi_cache_ts: dict[int, float] = {}
        self._smi_cache_lock = threading.Lock()

        # NVML: initialized lazily in _ensure_nvml(). Held for the
        # lifetime of the backend so REST and WS handlers don't fight
        # over init/shutdown.
        self._pynvml = None
        self._nvml_inited = False
        self._nvml_lock = threading.Lock()

    def initialize(self) -> bool:
        import platform
        if platform.system().lower() != "linux":
            return False

        try:
            # Check if nvidia-smi exists and works
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return False

            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    try:
                        idx = int(parts[0])
                        name = parts[1]
                        vram_mb = int(parts[2]) if parts[2].isdigit() else 0
                        self._gpu_info.append({
                            'index': idx,
                            'name': name,
                            'vram_bytes': vram_mb * 1024 * 1024,
                        })
                    except (ValueError, IndexError):
                        continue

            self._gpu_count = len(self._gpu_info)
            if self._gpu_count == 0:
                return False

            self.gpu_count = self._gpu_count
            self.gpu_names = [info['name'] for info in self._gpu_info]
            self.available = True
            self._initialized = True

            # Try to bring up NVML once. Failure is non-fatal — we'll
            # fall back to nvidia-smi only.
            self._ensure_nvml()

            logger.info(f"Linux NVIDIA: {self.gpu_count} GPU(s) via nvidia-smi")
            return True

        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.debug("Linux NVIDIA: nvidia-smi not available")
        except Exception as e:
            logger.error(f"Linux NVIDIA init error: {e}")

        return False

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        # Fast path: serve cached result if it's still fresh. This is
        # the common case when REST and WS both call us within 500ms.
        now = time.time()
        cached = self._smi_cache.get(gpu_id)
        cached_ts = self._smi_cache_ts.get(gpu_id, 0.0)
        if cached is not None and (now - cached_ts) < _SMI_CACHE_TTL:
            return cached

        # Slow path: actually run nvidia-smi.
        try:
            if gpu_id >= len(self._gpu_info):
                return HardwareStats(
                    gpu_id=gpu_id,
                    vendor="nvidia",
                    is_available=False,
                    error_message=f"GPU {gpu_id} not found",
                )

            info = self._gpu_info[gpu_id]
            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=info['name'],
                vendor="nvidia",
                driver="nvidia-smi",
                memory_total=info['vram_bytes'],
                is_available=True,
            )

            # Query real-time stats via nvidia-smi
            try:
                result = subprocess.run(
                    ["nvidia-smi",
                     f"--id={gpu_id}",
                     "--query-gpu=utilization.gpu,utilization.memory,memory.used,"
                     "temperature.gpu,fan.speed,clocks.current.graphics,"
                     "clocks.current.memory,power.draw",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"Linux NVIDIA: nvidia-smi timed out for GPU {gpu_id}"
                )
                # Reuse last known good reading if we have one.
                if cached is not None:
                    return cached
                return HardwareStats(
                    gpu_id=gpu_id,
                    gpu_name=self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"NVIDIA GPU {gpu_id}",
                    vendor="nvidia",
                    driver="nvidia-smi",
                    memory_total=info['vram_bytes'],
                    is_available=True,
                )

            if result.returncode == 0 and result.stdout.strip():
                parts = [p.strip() for p in result.stdout.strip().split(',')]
                if len(parts) >= 8:
                    try:
                        stats.utilization_gpu = min(100.0, float(parts[0]))
                        stats.utilization_memory = min(100.0, float(parts[1]))
                        mem_used_mb = int(float(parts[2]))
                        stats.memory_used = mem_used_mb * 1024 * 1024
                        stats.memory_free = max(0, info['vram_bytes'] - stats.memory_used)
                        stats.temperature = float(parts[3])
                        try:
                            stats.fan_speed = int(float(parts[4]))
                        except (ValueError, IndexError):
                            pass
                        stats.core_clock = int(float(parts[5]))
                        stats.memory_clock = int(float(parts[6]))
                        stats.power_draw = float(parts[7])
                    except (ValueError, IndexError) as e:
                        logger.warning(
                            f"Linux NVIDIA: failed to parse nvidia-smi output "
                            f"for GPU {gpu_id}: {e}"
                        )
            else:
                # nvidia-smi failed — emit a one-shot warning so the user
                # knows overlay readings are stale, then fall back to sysfs
                # temp if available.
                logger.warning(
                    f"Linux NVIDIA: nvidia-smi returned non-zero for GPU {gpu_id} "
                    f"(rc={result.returncode}); overlay will show stale stats"
                )
                stats.temperature = self._get_temp_fallback(gpu_id)

            # === FAN FALLBACK ===
            # nvidia-smi fan.speed returns 0 or "[Not Supported]" on many
            # newer GPUs (RTX 40/50, server cards, some notebook drivers).
            # When that happens, fall back to pynvml NVML which uses the
            # driver directly and exposes fan on most cards that have one.
            if stats.fan_speed <= 0:
                fallback_fan = self._read_fan_via_nvml(gpu_id)
                if fallback_fan > 0:
                    stats.fan_speed = fallback_fan

            # Store in cache for subsequent callers.
            with self._smi_cache_lock:
                self._smi_cache[gpu_id] = stats
                self._smi_cache_ts[gpu_id] = time.time()
            return stats

        except Exception as e:
            logger.error(f"Linux NVIDIA get_stats({gpu_id}) error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                vendor="nvidia",
                is_available=False,
                error_message=str(e),
            )

    def _get_temp_fallback(self, gpu_id: int) -> float:
        """Fallback: read temperature from sysfs for NVIDIA."""
        try:
            # Try /sys/class/drm/card*/device/hwmon for NVIDIA
            import os
            drm_path = "/sys/class/drm"
            if os.path.exists(drm_path):
                for entry in sorted(os.listdir(drm_path)):
                    if entry.startswith(f"card{gpu_id}") and "-" not in entry:
                        card_path = os.path.join(drm_path, entry)
                        hwmon_dir = os.path.join(card_path, "device", "hwmon")
                        if os.path.exists(hwmon_dir):
                            for hwmon_entry in os.listdir(hwmon_dir):
                                hwmon_path = os.path.join(hwmon_dir, hwmon_entry)
                                for temp_entry in os.listdir(hwmon_path):
                                    if temp_entry.startswith("temp") and temp_entry.endswith("_input"):
                                        try:
                                            with open(os.path.join(hwmon_path, temp_entry), 'r') as f:
                                                raw = int(f.read().strip())
                                            celsius = raw / 1000.0
                                            if 20 <= celsius <= 120:
                                                return celsius
                                        except (ValueError, OSError):
                                            pass
        except Exception:
            pass
        return 0.0

    def _ensure_nvml(self) -> bool:
        """Initialize NVML once. Safe to call repeatedly — no-op after success."""
        with self._nvml_lock:
            if self._nvml_inited:
                return self._pynvml is not None
            try:
                import pynvml  # type: ignore
            except ImportError:
                logger.debug("Linux NVIDIA: pynvml not installed, NVML fallback unavailable")
                self._nvml_inited = True  # don't keep retrying every call
                self._pynvml = None
                return False
            try:
                pynvml.nvmlInit()
                self._pynvml = pynvml
                self._nvml_inited = True
                logger.debug("Linux NVIDIA: NVML initialized for fan fallback")
                return True
            except Exception as e:
                # Driver not loaded, no permission, no NVIDIA hardware —
                # all recoverable. Don't re-init per call.
                logger.debug(f"Linux NVIDIA: NVML init failed: {e}")
                self._pynvml = None
                self._nvml_inited = True
                return False

    def _read_fan_via_nvml(self, gpu_id: int) -> int:
        """Fallback fan reader using pynvml.

        ``nvidia-smi``'s ``fan.speed`` query is unreliable on RTX 40/50 and
        many notebook drivers — it often reports 0 or ``[Not Supported]`` even
        when the driver has full sensor data. NVML's
        ``nvmlDeviceGetFanSpeed`` uses the driver directly and exposes the
        fan duty cycle as a percent (0-100) on almost every discrete
        NVIDIA GPU.

        Returns:
            Fan duty cycle in percent (0-100), or 0 if unavailable.
        """
        if not self._ensure_nvml() or self._pynvml is None:
            return 0
        try:
            handle = self._pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
            speed = int(self._pynvml.nvmlDeviceGetFanSpeed(handle))
            # NVML returns 0 for fanless / passive cards — that is a real
            # value, not an error. Caller treats >0 as "have a fan reading".
            return max(0, min(100, speed))
        except Exception as e:
            # NotSupported / NotFound / Unknown — common on consumer cards
            # with locked VBIOS or APU-like configurations.
            logger.debug(f"Linux NVIDIA: NVML fan read failed for GPU {gpu_id}: {e}")
            return 0

    def close(self):
        """Release NVML handle and clear caches."""
        with self._nvml_lock:
            if self._nvml_inited and self._pynvml is not None:
                try:
                    self._pynvml.nvmlShutdown()
                except Exception as e:
                    logger.debug(f"Linux NVIDIA: NVML shutdown error: {e}")
                self._pynvml = None
            self._nvml_inited = False
        with self._smi_cache_lock:
            self._smi_cache.clear()
            self._smi_cache_ts.clear()
