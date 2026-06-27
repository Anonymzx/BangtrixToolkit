"""
Universal Fallback Backend
===========================
Uses psutil for basic system memory info (last resort on ANY OS).
Provides safe defaults when no GPU backend is available.
"""

import logging
from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


class FallbackBackend(MonitorBackend):
    """psutil fallback — works on both Windows and Linux"""
    name = "psutil-fallback"

    def initialize(self) -> bool:
        try:
            import psutil
            self.available = True
            self.gpu_count = 1
            self.gpu_names = ["System RAM (no GPU backend)"]
            logger.info("Fallback: psutil active")
            return True
        except ImportError:
            logger.debug("Fallback: psutil not installed — using manual /proc/meminfo")
            try:
                # Manual fallback: read /proc/meminfo on Linux
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            self.available = True
                            self.gpu_count = 1
                            self.gpu_names = ["System RAM (no GPU backend)"]
                            return True
            except Exception:
                pass
            return False

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        try:
            import psutil
            svmem = psutil.virtual_memory()
            return HardwareStats(
                gpu_id=gpu_id,
                gpu_name=self.gpu_names[0] if self.gpu_names else "System RAM",
                vendor="unknown",
                driver="psutil-fallback",
                is_apu=True,
                utilization_memory=(svmem.used / svmem.total * 100) if svmem.total > 0 else 0,
                memory_total=svmem.total,
                memory_used=svmem.used,
                memory_free=svmem.available,
                memory_shared=svmem.total,
                is_available=True,
            )
        except ImportError:
            # Manual /proc/meminfo fallback
            try:
                total = 0
                available = 0
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            total = int(line.split()[1]) * 1024
                        elif line.startswith('MemAvailable:'):
                            available = int(line.split()[1]) * 1024
                used = total - available
                return HardwareStats(
                    gpu_id=gpu_id,
                    gpu_name=self.gpu_names[0] if self.gpu_names else "System RAM",
                    vendor="unknown",
                    driver="manual-fallback",
                    is_apu=True,
                    utilization_memory=(used / total * 100) if total > 0 else 0,
                    memory_total=total,
                    memory_used=used,
                    memory_free=available,
                    memory_shared=total,
                    is_available=True,
                )
            except Exception as e:
                return HardwareStats(
                    gpu_id=gpu_id,
                    is_available=False,
                    error_message=str(e),
                )