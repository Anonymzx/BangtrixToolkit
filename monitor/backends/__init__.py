"""
Hardware Monitor Backends
=========================
Backend modules for universal GPU/Hardware monitoring.
Auto-detects OS and GPU vendor at runtime.

Windows Backends:
  - pdh_backend: PDH Performance Counters (native — Task Manager source)
  - powershell_backend: PowerShell Get-Counter fallback
  - windows_nvml: NVIDIA via pynvml (optional)
  - adl_backend: AMD Display Library (legacy)

Linux Backends:
  - linux_amdgpu: AMD via /sys/class/drm/ sysfs — no ROCm needed
  - linux_nvidia: NVIDIA via nvidia-smi CLI parsing
  - linux_intel: Intel via sysfs + hwmon
  - linux_generic: Generic fallback via /proc + /sys

Universal Fallback:
  - fallback: psutil-based system RAM fallback (last resort)
"""

from .base import MonitorBackend, HardwareStats, AMDGPUStats

# Windows backends
from .pdh_backend import PDHBackend
from .powershell_backend import PowerShellBackend
from .adl_backend import ADLBackend
from .windows_nvml import WindowsNVIDIABackend

# Linux backends
from .linux_amdgpu import LinuxAMDGPUBackend
from .linux_nvidia import LinuxNVIDIABackend
from .linux_intel import LinuxIntelBackend
from .linux_generic import LinuxGenericBackend

# Universal fallback
from .fallback import FallbackBackend
from .amd_smi_backend import AMDSensorBackend

__all__ = [
    "MonitorBackend",
    "HardwareStats",
    "AMDGPUStats",
    "PDHBackend",
    "AMDSensorBackend",
    "PowerShellBackend",
    "ADLBackend",
    "WindowsNVIDIABackend",
    "LinuxAMDGPUBackend",
    "LinuxNVIDIABackend",
    "LinuxIntelBackend",
    "LinuxGenericBackend",
    "FallbackBackend",
]