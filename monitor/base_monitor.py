"""
Universal Hardware Monitor
===========================
Auto-detects OS, GPU vendor, and selects the best available backend.
Supports Windows and Linux with all GPU vendors (AMD, NVIDIA, Intel).

Architecture:
  1. Detector layer: Identify OS + GPU vendor(s) using standard library
  2. Backend selection: Try backends in priority order based on OS + vendor
  3. Stats fetching: Thread-safe, non-blocking API

IMPORTANT: All heavy initialization (detection, backend trial) runs in
a background daemon thread to avoid blocking ComfyUI startup.
"""

import logging
import importlib
import threading
from typing import Optional, List

from .detector import detect_hardware
from .backends.base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


class UniversalMonitor:
    """Universal hardware monitor with auto-detection and fallback chain.

    Initialization happens asynchronously in a daemon thread so that
    this class can be instantiated immediately without blocking.
    """

    def __init__(self):
        self.available = False
        self.os_type: str = "unknown"
        self.vendor: str = "unknown"
        self.gpu_count = 0
        self.gpu_names: List[str] = []
        self.has_apu: bool = False
        self.driver: str = ""
        self._backend: Optional[MonitorBackend] = None
        self._ready = False          # True only after initialize() completes
        self._init_error: Optional[str] = None

        # Start background initialization in a daemon thread
        self._init_thread = threading.Thread(target=self._background_init, daemon=True)
        self._init_thread.start()

    def _background_init(self):
        """Wrapper that runs _initialize() in a background daemon thread."""
        try:
            self._initialize()
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"Universal Monitor: background init failed: {e}")
        finally:
            self._ready = True

    def wait_ready(self, timeout: float = 10.0) -> bool:
        """Block until initialization finishes (for callers that can wait).

        Returns True if initialization completed successfully, False if
        timeout or failure.
        """
        if self._ready:
            return self.available
        if self._init_thread and self._init_thread.is_alive():
            self._init_thread.join(timeout=timeout)
        return self.available

    @property
    def ready(self) -> bool:
        """True once background initialization has completed (success or fail)."""
        return self._ready

    def _initialize(self):
        """Detect hardware and select best backend (runs in background thread)."""
        # Step 1: Detect OS and GPU hardware
        hw_info = detect_hardware()
        self.os_type = hw_info.get('os', 'unknown')
        self.vendor = hw_info.get('primary_vendor', 'unknown')
        self.has_apu = hw_info.get('has_apu', False)
        gpu_list = hw_info.get('gpus', [])

        # Step 2: Try backends in priority order based on OS + vendor
        backends = self._get_backend_chain()

        for name, backend_cls in backends:
            try:
                backend = backend_cls()
                if backend.initialize():
                    self._backend = backend
                    self.available = True
                    self.gpu_count = backend.gpu_count
                    self.gpu_names = backend.gpu_names
                    # Only override vendor if backend has a real detection
                    # (detector.py via registry/WMI is more reliable than backend)
                    if backend.vendor and backend.vendor not in ("unknown", "virtual"):
                        self.vendor = backend.vendor
                    self.driver = backend.name
                    logger.info(
                        f"Universal Monitor: using {name} "
                        f"| OS={self.os_type} Vendor={self.vendor} "
                        f"| {self.gpu_count} GPU(s) APU={self.has_apu}"
                    )
                    return
            except Exception as e:
                logger.debug(f"Universal Monitor: {name} failed: {e}")

        logger.error("Universal Monitor: no backend available")

    def _get_backend_chain(self) -> list:
        """Get ordered list of (name, class) tuples to try."""
        chain = []

        if self.os_type == 'windows':
            # For AMD: try ROCm first (hipInfo + amd-smi), then ADL (temp/fan), then PDH (utilization/VRAM)
            if self.vendor == 'amd':
                chain = [
                    ("windows-rocm", self._import_backend("rocm_backend", "ROCMBackend")),
                    ("windows-adl", self._import_backend("adl_backend", "ADLBackend")),
                    ("windows-pdh", self._import_backend("pdh_backend", "PDHBackend")),
                    ("windows-powershell", self._import_backend("powershell_backend", "PowerShellBackend")),
                    ("windows-nvml", self._import_backend("windows_nvml", "WindowsNVIDIABackend")),
                ]
            elif self.vendor == 'nvidia':
                chain = [
                    ("windows-nvml", self._import_backend("windows_nvml", "WindowsNVIDIABackend")),
                    ("windows-pdh", self._import_backend("pdh_backend", "PDHBackend")),
                    ("windows-powershell", self._import_backend("powershell_backend", "PowerShellBackend")),
                    ("windows-adl", self._import_backend("adl_backend", "ADLBackend")),
                ]
            else:
                chain = [
                    ("windows-pdh", self._import_backend("pdh_backend", "PDHBackend")),
                    ("windows-powershell", self._import_backend("powershell_backend", "PowerShellBackend")),
                    ("windows-nvml", self._import_backend("windows_nvml", "WindowsNVIDIABackend")),
                    ("windows-adl", self._import_backend("adl_backend", "ADLBackend")),
                ]

        elif self.os_type == 'linux':
            if self.vendor == 'amd':
                chain = [
                    ("linux-amdgpu", self._import_backend("linux_amdgpu", "LinuxAMDGPUBackend")),
                    ("linux-nvidia", self._import_backend("linux_nvidia", "LinuxNVIDIABackend")),
                    ("linux-intel", self._import_backend("linux_intel", "LinuxIntelBackend")),
                    ("linux-generic", self._import_backend("linux_generic", "LinuxGenericBackend")),
                ]
            elif self.vendor == 'nvidia':
                chain = [
                    ("linux-nvidia", self._import_backend("linux_nvidia", "LinuxNVIDIABackend")),
                    ("linux-amdgpu", self._import_backend("linux_amdgpu", "LinuxAMDGPUBackend")),
                    ("linux-intel", self._import_backend("linux_intel", "LinuxIntelBackend")),
                    ("linux-generic", self._import_backend("linux_generic", "LinuxGenericBackend")),
                ]
            elif self.vendor == 'intel':
                chain = [
                    ("linux-intel", self._import_backend("linux_intel", "LinuxIntelBackend")),
                    ("linux-nvidia", self._import_backend("linux_nvidia", "LinuxNVIDIABackend")),
                    ("linux-amdgpu", self._import_backend("linux_amdgpu", "LinuxAMDGPUBackend")),
                    ("linux-generic", self._import_backend("linux_generic", "LinuxGenericBackend")),
                ]
            else:
                chain = [
                    ("linux-amdgpu", self._import_backend("linux_amdgpu", "LinuxAMDGPUBackend")),
                    ("linux-nvidia", self._import_backend("linux_nvidia", "LinuxNVIDIABackend")),
                    ("linux-intel", self._import_backend("linux_intel", "LinuxIntelBackend")),
                    ("linux-generic", self._import_backend("linux_generic", "LinuxGenericBackend")),
                ]

        # Always append universal fallback at the end
        chain.append(("psutil-fallback", self._import_backend("fallback", "FallbackBackend")))

        # Filter out None values (failed imports)
        return [(name, cls) for name, cls in chain if cls is not None]

    def _import_backend(self, module_name: str, class_name: str):
        """Safely import a backend class."""
        try:
            mod = importlib.import_module(f".backends.{module_name}", package="monitor")
            return getattr(mod, class_name)
        except Exception as e:
            logger.debug(f"Cannot import {module_name}.{class_name}: {e}")
            return None

    def get_gpu_stats(self, gpu_id: int = 0) -> HardwareStats:
        """Get stats for a specific GPU. Returns safe fallback on error."""
        # If backend is not ready yet, return a placeholder with "loading" status
        if not self._ready:
            return HardwareStats(
                gpu_id=gpu_id,
                gpu_name="Detecting Hardware...",
                vendor=self.vendor,
                is_available=False,
                is_loading=True,
                error_message="Hardware detection in progress",
            )
        if not self._backend or not self.available:
            return HardwareStats(
                gpu_id=gpu_id,
                gpu_name=self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else "N/A",
                vendor=self.vendor,
                is_available=False,
                error_message="No backend available",
            )
        try:
            stats = self._backend.get_stats(gpu_id)
            # Ensure vendor is set (prefer detected vendor over backend's)
            stats.vendor = self.vendor if (self.vendor and self.vendor != "unknown") else (stats.vendor or "unknown")
            if not stats.gpu_name and gpu_id < len(self.gpu_names):
                stats.gpu_name = self.gpu_names[gpu_id]
            if not stats.driver:
                stats.driver = self.driver
            return stats
        except Exception as e:
            return HardwareStats(
                gpu_id=gpu_id,
                gpu_name=self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else "N/A",
                vendor=self.vendor,
                is_available=False,
                error_message=str(e),
            )

    def get_all_gpu_stats(self) -> List[HardwareStats]:
        """Get stats for all detected GPUs."""
        if not self._ready or not self._backend or self.gpu_count == 0:
            return []
        return [self.get_gpu_stats(i) for i in range(self.gpu_count)]

    def close(self):
        """Cleanup backend resources."""
        if self._backend:
            self._backend.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Singleton
_universal_monitor = None
_monitor_lock = threading.Lock()


def get_universal_monitor() -> UniversalMonitor:
    """Get or create the singleton UniversalMonitor instance."""
    global _universal_monitor
    if _universal_monitor is None:
        with _monitor_lock:
            if _universal_monitor is None:
                _universal_monitor = UniversalMonitor()
    return _universal_monitor