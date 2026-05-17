"""
Linux AMD GPU Backend
=====================
Reads GPU stats from Linux sysfs (/sys/class/drm/) and hwmon for AMD GPUs.
Zero external dependencies — uses standard library only.

Data sources:
  - GPU utilization: /sys/class/drm/card*/device/gpu_busy_percent
  - VRAM: /sys/class/drm/card*/device/mem_info_vram_total
           /sys/class/drm/card*/device/mem_info_vram_used
  - Temperature: /sys/class/drm/card*/device/hwmon/hwmon*/temp1_input
  - Core clock: /sys/class/drm/card*/device/pp_dpm_sclk (average from PP table)
  - Power: /sys/class/drm/card*/device/hwmon/hwmon*/power1_average

APU Support:
  - APUs with shared memory: memory_total=0, memory_shared=system_RAM
  - Detects APU by checking VRAM size < 512MB
"""

import logging
import os
import time
from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


class LinuxAMDGPUBackend(MonitorBackend):
    """AMD GPU monitoring on Linux via sysfs + hwmon"""
    name = "linux-amdgpu-sysfs"

    def __init__(self):
        super().__init__()
        self.vendor = "amd"
        self._card_paths: list[str] = []
        self._vram_total: int = 0
        self._is_apu: bool = False
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
            self._find_amd_cards()
            if not self._card_paths:
                return False

            self._detect_vram()
            self._detect_hwmon()
            self._detect_system_ram()

            self.gpu_count = len(self._card_paths)
            self.gpu_names = [f"AMD GPU {i}" for i in range(self.gpu_count)]
            self.available = True

            logger.info(
                f"Linux AMD: {self.gpu_count} GPU(s), "
                f"VRAM={self._vram_total / (1024*1024):.0f}MB, "
                f"APU={self._is_apu}"
            )
            return True
        except Exception as e:
            logger.error(f"Linux AMD init error: {e}")
            return False

    def _find_amd_cards(self):
        """Find AMD GPU card directories in /sys/class/drm/"""
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
                    if '1002' in vendor_id or 'amd' in vendor_id:
                        self._card_paths.append(card_path)
                except Exception:
                    pass

            # Fallback: check for amdgpu driver
            if not self._card_paths or card_path != self._card_paths[-1]:
                if os.path.exists(os.path.join(card_path, "device", "gpu_busy_percent")):
                    if card_path not in self._card_paths:
                        self._card_paths.append(card_path)

    def _detect_vram(self):
        """Read VRAM total from sysfs. Detect APU shared memory."""
        vram_total = 0
        for card_path in self._card_paths:
            vram_file = os.path.join(card_path, "device", "mem_info_vram_total")
            if os.path.exists(vram_file):
                try:
                    with open(vram_file, 'r') as f:
                        val = int(f.read().strip())
                    if val > vram_total:
                        vram_total = val
                except (ValueError, OSError):
                    pass

        self._vram_total = vram_total

        # APU detection: < 512MB VRAM means shared memory
        if 0 < vram_total < 512 * 1024 * 1024:
            self._is_apu = True
            self._vram_total = vram_total  # Keep actual value, even if small
        elif vram_total == 0:
            self._is_apu = True  # Likely APU with no dedicated VRAM reporting

    def _detect_hwmon(self):
        """Find hwmon paths for AMD GPU temperatures."""
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
                            if 'amdgpu' in name:
                                self._hwmon_paths.append(hwmon_path)
                        except Exception:
                            pass

    def _detect_system_ram(self):
        """Read total system RAM for APU shared memory tracking."""
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        parts = line.split()
                        if len(parts) >= 2:
                            self._system_ram_total = int(parts[1]) * 1024
                        break
        except Exception:
            self._system_ram_total = 8 * 1024 * 1024 * 1024  # 8GB fallback

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
                    vendor="amd",
                    is_available=False,
                    error_message=f"GPU {gpu_id} not found",
                )

            card_path = self._card_paths[gpu_id]
            name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}"

            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=name,
                vendor="amd",
                driver="amdgpu-sysfs",
                is_apu=self._is_apu,
                is_available=True,
            )

            # GPU Utilization (%)
            util_val = self._read_sysfs(os.path.join(card_path, "device", "gpu_busy_percent"))
            if util_val:
                try:
                    stats.utilization_gpu = min(100.0, max(0.0, float(util_val)))
                except ValueError:
                    pass

            # VRAM
            vram_used_file = os.path.join(card_path, "device", "mem_info_vram_used")
            vram_used = self._read_sysfs(vram_used_file)
            if vram_used and self._vram_total > 0:
                try:
                    used = int(vram_used)
                    stats.memory_used = used
                    stats.memory_total = self._vram_total
                    stats.memory_free = max(0, self._vram_total - used)
                    if self._vram_total > 0:
                        stats.utilization_memory = (used / self._vram_total) * 100.0
                except ValueError:
                    pass

            # APU shared memory fallback
            if self._is_apu and stats.memory_total == 0:
                try:
                    import psutil
                    svmem = psutil.virtual_memory()
                    stats.memory_shared = self._system_ram_total
                    stats.memory_used = int(svmem.used * 0.25)  # Estimate GPU portion
                    stats.utilization_memory = svmem.percent
                except ImportError:
                    stats.memory_shared = self._system_ram_total

            # Temperature (cached)
            stats.temperature = self._get_temperature()

            # Core Clock
            clock_val = self._read_sysfs(os.path.join(card_path, "device", "pp_dpm_sclk"))
            if clock_val:
                try:
                    # Parse average clock from PP table
                    lines = clock_val.strip().split('\n')
                    for line in lines:
                        if 'Mhz' in line or 'MHz' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                # Extract number before MHz
                                import re
                                match = re.search(r'(\d+)\s*Mhz', parts[-1], re.IGNORECASE)
                                if match:
                                    stats.core_clock = int(match.group(1))
                                    break
                except Exception:
                    pass

            # Power draw
            power = self._read_power(card_path)
            if power is not None:
                stats.power_draw = power

            return stats

        except Exception as e:
            logger.error(f"Linux AMD get_stats({gpu_id}) error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                vendor="amd",
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
                        temp_file = os.path.join(hwmon_path, entry)
                        try:
                            with open(temp_file, 'r') as f:
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

    def _read_power(self, card_path: str) -> Optional[float]:
        """Read GPU power draw from hwmon."""
        for hwmon_path in self._hwmon_paths:
            try:
                power_file = os.path.join(hwmon_path, "power1_average")
                if os.path.exists(power_file):
                    with open(power_file, 'r') as f:
                        raw = int(f.read().strip())
                    # Convert microwatts to watts
                    return raw / 1_000_000.0
            except (ValueError, OSError):
                pass
        return None

    def close(self):
        pass