"""
BangtrixToolkit — Universal Hardware Monitoring Package
=======================================================
Auto-detects OS, GPU vendor, and selects the best monitoring backend.
Supports Windows and Linux with AMD, NVIDIA, and Intel GPUs.

Usage:
    from monitor import get_universal_monitor
    monitor = get_universal_monitor()
    stats = monitor.get_gpu_stats(0)
    print(stats.gpu_name, stats.vendor, stats.temperature)
"""

from .base_monitor import get_universal_monitor, UniversalMonitor
from .backends.base import HardwareStats, MonitorBackend
from .process_monitor import get_process_monitor, ComfyProcessMonitor, GenerationRecord
from .hw_server import get_hw_server, HardwareMonitorServer

__all__ = [
    "get_universal_monitor",
    "UniversalMonitor",
    "HardwareStats",
    "MonitorBackend",
    "get_process_monitor",
    "ComfyProcessMonitor",
    "GenerationRecord",
    "get_hw_server",
    "HardwareMonitorServer",
]