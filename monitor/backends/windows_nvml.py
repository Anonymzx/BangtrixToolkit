"""
Windows NVIDIA Backend (pynvml)
===============================
Uses pynvml for maximum accuracy on NVIDIA GPUs on Windows.
Gracefully falls back if pynvml is not installed or fails.

This is the PREFERRED backend for NVIDIA on Windows — uses the
NVIDIA Management Library directly for precise metrics.
"""

import logging
from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


class WindowsNVIDIABackend(MonitorBackend):
    """NVIDIA GPU monitoring on Windows via pynvml"""
    name = "windows-nvml"

    def __init__(self):
        super().__init__()
        self.vendor = "nvidia"
        self._nvml_available = False
        self._device_handles = []
        self._nvml = None

    def initialize(self) -> bool:
        import platform
        if platform.system().lower() != "windows":
            return False

        try:
            import pynvml
            self._nvml = pynvml
            pynvml.nvmlInit()

            device_count = pynvml.nvmlDeviceGetCount()
            if device_count == 0:
                pynvml.nvmlShutdown()
                return False

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                self._device_handles.append(handle)
                try:
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode('utf-8', errors='replace')
                    self.gpu_names.append(name)
                except Exception:
                    self.gpu_names.append(f"NVIDIA GPU {i}")

            self.gpu_count = device_count
            self._nvml_available = True
            self.available = True

            logger.info(f"Windows NVIDIA: {self.gpu_count} GPU(s) via pynvml")
            return True

        except ImportError:
            logger.debug("Windows NVIDIA: pynvml not installed")
        except Exception as e:
            logger.debug(f"Windows NVIDIA init error: {e}")
            try:
                if self._nvml:
                    self._nvml.nvmlShutdown()
            except Exception:
                pass

        return False

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        try:
            if gpu_id >= len(self._device_handles) or not self._nvml:
                return HardwareStats(
                    gpu_id=gpu_id,
                    vendor="nvidia",
                    is_available=False,
                    error_message=f"GPU {gpu_id} not found",
                )

            handle = self._device_handles[gpu_id]
            nvml = self._nvml
            name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"NVIDIA GPU {gpu_id}"

            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=name,
                vendor="nvidia",
                driver="pynvml",
                is_available=True,
            )

            # GPU Utilization
            try:
                util = nvml.nvmlDeviceGetUtilizationRates(handle)
                stats.utilization_gpu = float(util.gpu)
                stats.utilization_memory = float(util.memory)
            except Exception:
                pass

            # Memory
            try:
                mem_info = nvml.nvmlDeviceGetMemoryInfo(handle)
                stats.memory_total = mem_info.total
                stats.memory_used = mem_info.used
                stats.memory_free = mem_info.free
                if mem_info.total > 0:
                    stats.utilization_memory = (mem_info.used / mem_info.total) * 100.0
            except Exception:
                pass

            # Temperature
            try:
                temp = nvml.nvmlDeviceGetTemperature(handle, 0)  # GPU temp
                stats.temperature = float(temp)
            except Exception:
                pass

            # Fan speed
            try:
                fan = nvml.nvmlDeviceGetFanSpeed(handle)
                stats.fan_speed = int(fan)
            except Exception:
                pass

            # Clocks
            try:
                stats.core_clock = nvml.nvmlDeviceGetClockInfo(handle, 1)  # Graphics clock
                stats.memory_clock = nvml.nvmlDeviceGetClockInfo(handle, 2)  # Memory clock
            except Exception:
                pass

            # Power draw
            try:
                power = nvml.nvmlDeviceGetPowerUsage(handle)
                stats.power_draw = power / 1000.0  # Milliwatts to Watts
            except Exception:
                pass

            return stats

        except Exception as e:
            logger.error(f"Windows NVIDIA get_stats({gpu_id}) error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                vendor="nvidia",
                is_available=False,
                error_message=str(e),
            )

    def close(self):
        if self._nvml and self._nvml_available:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass