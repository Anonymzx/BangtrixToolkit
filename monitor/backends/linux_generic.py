"""
Linux Generic Backend (Fallback)
=================================
Fallback backend for Linux when no specific GPU driver is available.
Uses psutil for system-level stats and /proc/stat for CPU.

This is the LAST RESORT backend on Linux — provides basic system monitoring
when no GPU-specific backend is available.
"""

import logging
import os
import time
from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


class LinuxGenericBackend(MonitorBackend):
    """Generic Linux fallback monitoring"""
    name = "linux-generic"

    def __init__(self):
        super().__init__()
        self.vendor = "unknown"
        self._system_ram_total: int = 0

    def initialize(self) -> bool:
        import platform
        if platform.system().lower() != "linux":
            return False

        try:
            # Read system RAM
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

            self.gpu_count = 1
            self.gpu_names = ["System (no GPU driver detected)"]
            self.available = True

            logger.info(f"Linux Generic: fallback active, RAM={self._system_ram_total / (1024*1024*1024):.1f}GB")
            return True

        except Exception as e:
            logger.error(f"Linux Generic init error: {e}")
            return False

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        try:
            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=self.gpu_names[0] if self.gpu_names else "Linux System",
                vendor="unknown",
                driver="linux-generic",
                is_apu=True,  # Generic fallback, assume shared memory
                is_available=True,
            )

            # System RAM stats via psutil
            try:
                import psutil
                svmem = psutil.virtual_memory()
                stats.memory_shared = self._system_ram_total
                stats.memory_used = svmem.used
                stats.memory_free = svmem.available
                if self._system_ram_total > 0:
                    stats.utilization_memory = (svmem.used / self._system_ram_total) * 100.0
            except ImportError:
                pass

            # CPU temperature fallback
            stats.temperature = self._read_cpu_temp()

            return stats

        except Exception as e:
            logger.error(f"Linux Generic get_stats error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                is_available=False,
                error_message=str(e),
            )

    def _read_cpu_temp(self) -> float:
        """Read CPU temperature as a proxy."""
        try:
            # Try thermal zone
            tz_path = "/sys/class/thermal"
            if os.path.exists(tz_path):
                for entry in sorted(os.listdir(tz_path)):
                    if entry.startswith("thermal_zone"):
                        temp_file = os.path.join(tz_path, entry, "temp")
                        if os.path.exists(temp_file):
                            try:
                                with open(temp_file, 'r') as f:
                                    raw = int(f.read().strip())
                                celsius = raw / 1000.0
                                if 20 <= celsius <= 120:
                                    return celsius
                            except (ValueError, OSError):
                                pass
        except Exception:
            pass
        return 0.0

    def close(self):
        pass