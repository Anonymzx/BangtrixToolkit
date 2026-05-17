"""
Backend monitoring modules for AMD GPU stats.
Auto-detects best available backend.
"""

from .base import MonitorBackend, AMDGPUStats
from .pdh_backend import PDHBackend
from .powershell_backend import PowerShellBackend
from .adl_backend import ADLBackend
from .libre_hardware import LibreHardwareBackend
from .psutil_backend import PsutilBackend

__all__ = [
    "MonitorBackend",
    "AMDGPUStats",
    "PDHBackend",
    "PowerShellBackend",
    "ADLBackend",
    "LibreHardwareBackend",
    "PsutilBackend",
]
