"""
Base classes for hardware monitoring backends.
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class HardwareStats:
    """Normalized GPU/Hardware statistics from any backend"""
    gpu_id: int = 0
    gpu_name: str = ""
    vendor: str = "unknown"          # "amd" | "nvidia" | "intel" | "unknown"
    driver: str = ""                 # Backend driver name (e.g., "pdh", "nvml", "amdgpu-sysfs")
    utilization_gpu: float = 0.0     # 0-100%
    utilization_memory: float = 0.0  # 0-100%
    memory_total: int = 0            # Bytes (0 = shared/APU, use memory_shared)
    memory_used: int = 0             # Bytes
    memory_free: int = 0             # Bytes
    memory_shared: int = 0           # Bytes for APU/iGPU shared system RAM
    is_apu: bool = False             # True if APU/iGPU with shared memory
    temperature: float = 0.0         # Celsius
    fan_speed: int = 0               # 0-100%
    core_clock: int = 0              # MHz
    memory_clock: int = 0            # MHz
    power_draw: float = 0.0          # Watts
    is_available: bool = True
    is_loading: bool = False       # True while background init is in progress
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dict with explicit Python native types for safe JSON."""
        return {
            'gpu_id': int(self.gpu_id),
            'gpu_name': str(self.gpu_name or ""),
            'vendor': str(self.vendor or "unknown"),
            'driver': str(self.driver or ""),
            'is_apu': bool(self.is_apu),
            'utilization_gpu': round(float(self.utilization_gpu or 0), 1),
            'utilization_memory': round(float(self.utilization_memory or 0), 1),
            'memory_total': int(self.memory_total or 0),
            'memory_used': int(self.memory_used or 0),
            'memory_free': int(self.memory_free or 0),
            'memory_shared': int(self.memory_shared or 0),
            'temperature': round(float(self.temperature or 0), 1),
            'fan_speed': int(self.fan_speed or 0),
            'core_clock': int(self.core_clock or 0),
            'memory_clock': int(self.memory_clock or 0),
            'power_draw': round(float(self.power_draw or 0), 1),
            'is_available': bool(self.is_available),
        }

    def to_mb(self, value: int) -> float:
        """Convert bytes to MB safely"""
        return value / (1024.0 * 1024.0) if value > 0 else 0.0

    def safe_memory_pct(self) -> float:
        """Safe memory utilization percentage - handles APU shared memory"""
        if self.memory_total > 0:
            return (self.memory_used / self.memory_total) * 100.0
        if self.memory_shared > 0:
            return (self.memory_used / self.memory_shared) * 100.0
        return 0.0


# Backward compatibility alias
AMDGPUStats = HardwareStats


class MonitorBackend:
    """Base class for all monitoring backends"""

    name = "base"

    def __init__(self):
        self.available = False
        self.gpu_count = 0
        self.gpu_names: List[str] = []
        self.vendor: str = "unknown"

    def initialize(self) -> bool:
        """Detect hardware and prepare backend. Returns True if available."""
        raise NotImplementedError

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        """Get current stats for a GPU."""
        raise NotImplementedError

    def get_all_stats(self) -> List[HardwareStats]:
        """Get stats for all GPUs."""
        return [self.get_stats(i) for i in range(self.gpu_count)]

    def close(self):
        """Cleanup resources."""
        pass