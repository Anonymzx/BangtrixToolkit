"""
Linux Intel GPU Backend
=======================
Reads GPU stats from Linux sysfs for Intel GPUs (integrated + Arc).
Supports both integrated iGPUs and discrete Intel Arc GPUs.

Data sources:
  - GPU utilization: /sys/class/drm/card*/device/gt_cur_freq_mhz (relative)
  - Temperature: /sys/class/drm/card*/device/hwmon/hwmon*/temp1_input
  - Memory: Intel iGPUs use shared system RAM
  - Frequency: /sys/class/drm/card*/device/gt_act_freq_mhz

APU/iGPU handling:
  - Intel iGPUs always use shared memory
  - memory_total = 0, memory_shared = system RAM
  - No division by zero or "missing VRAM" errors
"""

import logging
import os
import time
from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


class LinuxIntelBackend(MonitorBackend):
    """Intel GPU monitoring on Linux via sysfs"""
    name = "linux-intel-sysfs"

    def __init__(self):
        super().__init__()
        self.vendor = "intel"
        self._card_paths: list[str] = []
        self._is_discrete: bool = False  # True for Arc dGPU
        self._system_ram_total: int = 0
        self._hwmon_paths: list[str] = []
        self._temp_cache_timestamp: float = 0
        self._cached_temp: float = 0.0
        self._TEMP_CACHE_SECONDS = 5.0

    def initialize(self) -> bool:
        import platform
        if platform.system().lower() != "linux":
            return False

        try:
            self._find_intel_cards()
            if not self._card_paths:
                return False

            self._detect_gpu_type()
            self._detect_hwmon()
            self._detect_system_ram()

            self.gpu_count = len(self._card_paths)
            self.gpu_names = [f"Intel GPU {i}" for i in range(self.gpu_count)]
            self.available = True

            logger.info(
                f"Linux Intel: {self.gpu_count} GPU(s), "
                f"dGPU={self._is_discrete}"
            )
            return True
        except Exception as e:
            logger.error(f"Linux Intel init error: {e}")
            return False

    def _find_intel_cards(self):
        """Find Intel GPU card directories."""
        drm_path = "/sys/class/drm"
        if not os.path.exists(drm_path):
            return

        for entry in sorted(os.listdir(drm_path)):
            if not entry.startswith("card") or "-" in entry:
                continue

            card_path = os.path.join(drm_path, entry)

            # Check vendor
            vendor_file = os.path.join(card_path, "device", "vendor")
            if os.path.exists(vendor_file):
                try:
                    with open(vendor_file, 'r') as f:
                        vendor_id = f.read().strip().lower()
                    if '8086' in vendor_id:
                        self._card_paths.append(card_path)
                except Exception:
                    pass

    def _detect_gpu_type(self):
        """Detect if Intel GPU is discrete (Arc) or integrated."""
        for card_path in self._card_paths:
            # Check for dedicated VRAM (Arc dGPU has this)
            vram_file = os.path.join(card_path, "device", "lmem_total")
            if os.path.exists(vram_file):
                try:
                    with open(vram_file, 'r') as f:
                        val = int(f.read().strip())
                    if val > 512 * 1024 * 1024:  # > 512MB = discrete
                        self._is_discrete = True
                        return
                except (ValueError, OSError):
                    pass

    def _detect_hwmon(self):
        """Find hwmon paths for Intel GPU temperatures."""
        for card_path in self._card_paths:
            hwmon_dir = os.path.join(card_path, "device", "hwmon")
            if os.path.exists(hwmon_dir):
                for hwmon_entry in os.listdir(hwmon_dir):
                    hwmon_path = os.path.join(hwmon_dir, hwmon_entry)
                    name_file = os.path.join(hwmon_path, "name")
                    if os.path.exists(name_file):
                        try:
                            with open(name_file, 'r') as f:
                                name = f.read().strip().lower()
                            if 'intel' in name or 'i915' in name:
                                self._hwmon_paths.append(hwmon_path)
                        except Exception:
                            pass

    def _detect_system_ram(self):
        """Read total system RAM for shared memory tracking."""
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        parts = line.split()
                        if len(parts) >= 2:
                            self._system_ram_total = int(parts[1]) * 1024
                        break
        except Exception:
            self._system_ram_total = 8 * 1024 * 1024 * 1024

    def _read_sysfs(self, path: str) -> Optional[str]:
        """Safely read a sysfs file."""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        return None

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        try:
            if gpu_id >= len(self._card_paths):
                return HardwareStats(
                    gpu_id=gpu_id,
                    vendor="intel",
                    is_available=False,
                    error_message=f"GPU {gpu_id} not found",
                )

            card_path = self._card_paths[gpu_id]
            name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"Intel GPU {gpu_id}"

            # Intel iGPUs always use shared memory — mark as APU
            is_apu = not self._is_discrete

            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=name,
                vendor="intel",
                driver="intel-sysfs",
                is_apu=is_apu,
                is_available=True,
            )

            # For discrete Arc GPUs, try to read dedicated VRAM
            if self._is_discrete:
                lmem_total = self._read_sysfs(os.path.join(card_path, "device", "lmem_total"))
                lmem_used = self._read_sysfs(os.path.join(card_path, "device", "lmem_used"))
                if lmem_total:
                    try:
                        total = int(lmem_total)
                        stats.memory_total = total
                        if lmem_used:
                            used = int(lmem_used)
                            stats.memory_used = used
                            stats.memory_free = max(0, total - used)
                            if total > 0:
                                stats.utilization_memory = (used / total) * 100.0
                    except ValueError:
                        pass

            # For integrated GPUs, report shared system RAM
            if is_apu and stats.memory_total == 0:
                stats.memory_shared = self._system_ram_total
                try:
                    import psutil
                    svmem = psutil.virtual_memory()
                    if stats.memory_used == 0:
                        stats.memory_used = int(svmem.used * 0.15)  # Estimate GPU portion
                    stats.utilization_memory = svmem.percent
                except ImportError:
                    pass

            # GPU utilization — estimate from frequency ratio
            gt_act_freq = self._read_sysfs(os.path.join(card_path, "device", "gt_act_freq_mhz"))
            gt_cur_freq = self._read_sysfs(os.path.join(card_path, "device", "gt_cur_freq_mhz"))
            gt_max_freq = self._read_sysfs(os.path.join(card_path, "device", "gt_max_freq_mhz"))

            if gt_act_freq and gt_max_freq:
                try:
                    act = float(gt_act_freq)
                    max_f = float(gt_max_freq)
                    if max_f > 0:
                        stats.utilization_gpu = min(100.0, (act / max_f) * 100.0)
                except ValueError:
                    pass
            elif gt_cur_freq and gt_max_freq:
                try:
                    cur = float(gt_cur_freq)
                    max_f = float(gt_max_freq)
                    if max_f > 0:
                        stats.utilization_gpu = min(100.0, (cur / max_f) * 100.0)
                except ValueError:
                    pass

            # Temperature (cached)
            stats.temperature = self._get_temperature()

            # Core clock
            if gt_act_freq:
                try:
                    stats.core_clock = int(float(gt_act_freq))
                except ValueError:
                    pass

            return stats

        except Exception as e:
            logger.error(f"Linux Intel get_stats({gpu_id}) error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                vendor="intel",
                is_available=False,
                error_message=str(e),
            )

    def _get_temperature(self) -> float:
        """Read GPU temperature from hwmon with caching."""
        now = time.time()
        if now - self._temp_cache_timestamp < self._TEMP_CACHE_SECONDS:
            return self._cached_temp

        temp = 0.0
        for hwmon_path in self._hwmon_paths:
            try:
                for entry in sorted(os.listdir(hwmon_path)):
                    if entry.startswith("temp") and entry.endswith("_input"):
                        try:
                            with open(os.path.join(hwmon_path, entry), 'r') as f:
                                raw = int(f.read().strip())
                            celsius = raw / 1000.0
                            if 20 <= celsius <= 120:
                                if celsius > temp:
                                    temp = celsius
                        except (ValueError, OSError):
                            pass
            except Exception:
                pass

        self._cached_temp = temp
        self._temp_cache_timestamp = now
        return temp

    def close(self):
        pass