"""
Base classes for monitoring backends.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class AMDGPUStats:
    """Normalized GPU statistics from any backend"""
    gpu_id: int = 0
    gpu_name: str = ""
    utilization_gpu: float = 0.0      # 0-100%
    utilization_memory: float = 0.0   # 0-100%
    memory_total: int = 0             # Bytes
    memory_used: int = 0              # Bytes
    memory_free: int = 0              # Bytes
    temperature: float = 0.0          # Celsius
    fan_speed: int = 0                # 0-100%
    core_clock: int = 0               # MHz
    memory_clock: int = 0             # MHz
    power_draw: float = 0.0           # Watts
    is_available: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'gpu_id': self.gpu_id,
            'gpu_name': self.gpu_name,
            'utilization_gpu': round(self.utilization_gpu, 1),
            'utilization_memory': round(self.utilization_memory, 1),
            'memory_total': self.memory_total,
            'memory_used': self.memory_used,
            'memory_free': self.memory_free,
            'temperature': round(self.temperature, 1),
            'fan_speed': self.fan_speed,
            'core_clock': self.core_clock,
            'memory_clock': self.memory_clock,
            'power_draw': round(self.power_draw, 1),
            'is_available': self.is_available,
        }


class MonitorBackend:
    """Base class for all monitoring backends"""

    name = "base"

    def __init__(self):
        self.available = False
        self.gpu_count = 0
        self.gpu_names: List[str] = []

    def initialize(self) -> bool:
        """Detect hardware and prepare backend. Returns True if available."""
        raise NotImplementedError

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        """Get current stats for a GPU."""
        raise NotImplementedError

    def get_all_stats(self) -> List[AMDGPUStats]:
        """Get stats for all GPUs."""
        return [self.get_stats(i) for i in range(self.gpu_count)]

    def close(self):
        """Cleanup resources."""
        pass