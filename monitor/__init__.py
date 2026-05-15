"""
BangtrixToolkit — Hardware Monitoring Package
===============================================
Auto-detects best GPU monitoring backend.

Usage:
    from monitor import get_amd_monitor
    monitor = get_amd_monitor()
    stats = monitor.get_gpu_stats(0)
    print(stats.gpu_name, stats.temperature)
"""

from .amd_monitor import get_amd_monitor, AMDMonitor, AMDGPUStats
from .process_monitor import get_process_monitor, ComfyProcessMonitor, GenerationRecord

__all__ = [
    "get_amd_monitor",
    "AMDMonitor",
    "AMDGPUStats",
    "get_process_monitor",
    "ComfyProcessMonitor",
    "GenerationRecord",
]