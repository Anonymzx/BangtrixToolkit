"""
AMD Monitor - Unified GPU Monitoring
=====================================
Auto-detects best available backend:
1. LibreHardwareMonitor (Temperature, Fan, Load, Clocks, Power)
2. ADL (AMD Display Library)
3. PowerShell Counters (Utilization, VRAM, GPU name)
4. psutil (System RAM fallback)

Usage:
    from monitor import get_amd_monitor
    monitor = get_amd_monitor()
    stats = monitor.get_gpu_stats(0)
    print(stats.gpu_name, stats.utilization_gpu, stats.temperature)
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

from .backends import (
    MonitorBackend, AMDGPUStats,
    PDHBackend,
    PowerShellBackend,
    ADLBackend,
    LibreHardwareBackend,
    PsutilBackend,
)

logger = logging.getLogger(__name__)


class AMDMonitor:
    """Unified monitor that auto-selects best available backend"""

    def __init__(self):
        self.available = False
        self.method = None
        self.gpu_count = 0
        self.gpu_names: List[str] = []
        self._backend: Optional[MonitorBackend] = None
        self._selected_backend_name: Optional[str] = None
        self._initialize()

    def _initialize(self):
        """Try backends in priority order"""
        backends = [
            ("pdh-counters", PDHBackend),              # #1: Windows PDH native (sumber Task Manager)
            ("libre-hardware-monitor", LibreHardwareBackend),  # #2: LHM (paling lengkap)
            ("powershell-counters", PowerShellBackend), # #3: PowerShell fallback
            ("adl", ADLBackend),                        # #4: AMD ADL
            ("psutil-fallback", PsutilBackend),          # #5: System RAM only
        ]

        for name, cls in backends:
            try:
                backend = cls()
                if backend.initialize():
                    self._backend = backend
                    self._selected_backend_name = name
                    self.available = True
                    self.gpu_count = backend.gpu_count
                    self.gpu_names = backend.gpu_names
                    self.method = name
                    logger.info(f"AMD Monitor: using {name} — {self.gpu_count} GPU(s)")
                    return
            except Exception as e:
                logger.debug(f"AMD Monitor: {name} failed: {e}")

        logger.error("AMD Monitor: no backend available")

    def get_gpu_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        """Get stats for a specific GPU"""
        if not self._backend or not self.available:
            return AMDGPUStats(
                gpu_id=gpu_id,
                is_available=False,
                error_message="No backend available"
            )
        try:
            stats = self._backend.get_stats(gpu_id)
            stats.gpu_name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else stats.gpu_name
            return stats
        except Exception as e:
            return AMDGPUStats(
                gpu_id=gpu_id,
                is_available=False,
                error_message=str(e)
            )

    def get_all_gpu_stats(self) -> List[AMDGPUStats]:
        """Get stats for all detected GPUs"""
        if not self._backend or self.gpu_count == 0:
            return []
        return [self.get_gpu_stats(i) for i in range(self.gpu_count)]

    def close(self):
        """Cleanup backend resources"""
        if self._backend:
            self._backend.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Singleton
_amd_monitor = None


def get_amd_monitor() -> AMDMonitor:
    global _amd_monitor
    if _amd_monitor is None:
        _amd_monitor = AMDMonitor()
    return _amd_monitor