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
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'gpu_id': self.gpu_id,
            'gpu_name': self.gpu_name,
            'vendor': self.vendor,
            'driver': self.driver,
            'is_apu': self.is_apu,
            'utilization_gpu': round(self.utilization_gpu, 1),
            'utilization_memory': round(self.utilization_memory, 1),
            'memory_total': self.memory_total,
            'memory_used': self.memory_used,
            'memory_free': self.memory_free,
            'memory_shared': self.memory_shared,
            'temperature': round(self.temperature, 1),
            'fan_speed': self.fan_speed,
            'core_clock': self.core_clock,
            'memory_clock': self.memory_clock,
            'power_draw': round(self.power_draw, 1),
            'is_available': self.is_available,
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