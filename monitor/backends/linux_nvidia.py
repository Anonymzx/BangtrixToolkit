"""
Linux NVIDIA GPU Backend
========================
Reads GPU stats from nvidia-smi on Linux.
Gracefully handles missing nvidia-smi or NVIDIA drivers.

Falls back to 0/N/A values if nvidia-smi fails or times out.
All subprocess calls have timeouts to prevent blocking.
"""

import logging
import subprocess
import json
import re
from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


class LinuxNVIDIABackend(MonitorBackend):
    """NVIDIA GPU monitoring on Linux via nvidia-smi"""
    name = "linux-nvidia-smi"

    def __init__(self):
        super().__init__()
        self.vendor = "nvidia"
        self._gpu_count = 0
        self._gpu_info: list[dict] = []
        self._initialized = False

    def initialize(self) -> bool:
        import platform
        if platform.system().lower() != "linux":
            return False

        try:
            # Check if nvidia-smi exists and works
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return False

            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    try:
                        idx = int(parts[0])
                        name = parts[1]
                        vram_mb = int(parts[2]) if parts[2].isdigit() else 0
                        self._gpu_info.append({
                            'index': idx,
                            'name': name,
                            'vram_bytes': vram_mb * 1024 * 1024,
                        })
                    except (ValueError, IndexError):
                        continue

            self._gpu_count = len(self._gpu_info)
            if self._gpu_count == 0:
                return False

            self.gpu_count = self._gpu_count
            self.gpu_names = [info['name'] for info in self._gpu_info]
            self.available = True
            self._initialized = True

            logger.info(f"Linux NVIDIA: {self.gpu_count} GPU(s) via nvidia-smi")
            return True

        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.debug("Linux NVIDIA: nvidia-smi not available")
        except Exception as e:
            logger.error(f"Linux NVIDIA init error: {e}")

        return False

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        try:
            if gpu_id >= len(self._gpu_info):
                return HardwareStats(
                    gpu_id=gpu_id,
                    vendor="nvidia",
                    is_available=False,
                    error_message=f"GPU {gpu_id} not found",
                )

            info = self._gpu_info[gpu_id]
            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=info['name'],
                vendor="nvidia",
                driver="nvidia-smi",
                memory_total=info['vram_bytes'],
                is_available=True,
            )

            # Query real-time stats via nvidia-smi
            result = subprocess.run(
                ["nvidia-smi",
                 f"--id={gpu_id}",
                 "--query-gpu=utilization.gpu,utilization.memory,memory.used,"
                 "temperature.gpu,fan.speed,clocks.current.graphics,"
                 "clocks.current.memory,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )

            if result.returncode == 0 and result.stdout.strip():
                parts = [p.strip() for p in result.stdout.strip().split(',')]
                if len(parts) >= 8:
                    try:
                        stats.utilization_gpu = min(100.0, float(parts[0]))
                        stats.utilization_memory = min(100.0, float(parts[1]))
                        mem_used_mb = int(float(parts[2]))
                        stats.memory_used = mem_used_mb * 1024 * 1024
                        stats.memory_free = max(0, info['vram_bytes'] - stats.memory_used)
                        stats.temperature = float(parts[3])
                        try:
                            stats.fan_speed = int(float(parts[4]))
                        except (ValueError, IndexError):
                            pass
                        stats.core_clock = int(float(parts[5]))
                        stats.memory_clock = int(float(parts[6]))
                        stats.power_draw = float(parts[7])
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Linux NVIDIA parse error: {e}")
            else:
                # nvidia-smi failed — return basic info without real-time stats
                stats.temperature = self._get_temp_fallback(gpu_id)

            return stats

        except subprocess.TimeoutExpired:
            logger.debug(f"Linux NVIDIA get_stats({gpu_id}) timed out")
            return HardwareStats(
                gpu_id=gpu_id,
                gpu_name=self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"NVIDIA GPU {gpu_id}",
                vendor="nvidia",
                driver="nvidia-smi",
                memory_total=self._gpu_info[gpu_id]['vram_bytes'] if gpu_id < len(self._gpu_info) else 0,
                is_available=True,
            )
        except Exception as e:
            logger.error(f"Linux NVIDIA get_stats({gpu_id}) error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                vendor="nvidia",
                is_available=False,
                error_message=str(e),
            )

    def _get_temp_fallback(self, gpu_id: int) -> float:
        """Fallback: read temperature from sysfs for NVIDIA."""
        try:
            # Try /sys/class/drm/card*/device/hwmon for NVIDIA
            import os
            drm_path = "/sys/class/drm"
            if os.path.exists(drm_path):
                for entry in sorted(os.listdir(drm_path)):
                    if entry.startswith(f"card{gpu_id}") and "-" not in entry:
                        card_path = os.path.join(drm_path, entry)
                        hwmon_dir = os.path.join(card_path, "device", "hwmon")
                        if os.path.exists(hwmon_dir):
                            for hwmon_entry in os.listdir(hwmon_dir):
                                hwmon_path = os.path.join(hwmon_dir, hwmon_entry)
                                for temp_entry in os.listdir(hwmon_path):
                                    if temp_entry.startswith("temp") and temp_entry.endswith("_input"):
                                        try:
                                            with open(os.path.join(hwmon_path, temp_entry), 'r') as f:
                                                raw = int(f.read().strip())
                                            celsius = raw / 1000.0
                                            if 20 <= celsius <= 120:
                                                return celsius
                                        except (ValueError, OSError):
                                            pass
        except Exception:
            pass
        return 0.0

    def close(self):
        pass