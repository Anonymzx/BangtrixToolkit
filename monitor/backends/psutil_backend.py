"""
Psutil Fallback Backend
=======================
Uses psutil for basic system memory info (last resort).
"""

import logging
from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)


class PsutilBackend(MonitorBackend):
    name = "psutil-fallback"

    def initialize(self) -> bool:
        try:
            import psutil
            self.available = True
            self.gpu_count = 1
            self.gpu_names = ["System RAM (no GPU backend)"]
            logger.info("Psutil Backend: fallback active")
            return True
        except ImportError:
            logger.debug("Psutil Backend: psutil not installed")
            return False

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        import psutil
        svmem = psutil.virtual_memory()
        return AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=self.gpu_names[0],
            utilization_gpu=0.0,
            utilization_memory=(svmem.used / svmem.total * 100) if svmem.total > 0 else 0,
            memory_total=svmem.total,
            memory_used=svmem.used,
            memory_free=svmem.available,
            is_available=True,
        )