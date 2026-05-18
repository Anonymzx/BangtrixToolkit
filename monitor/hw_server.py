"""
Universal Hardware Monitor Server
==================================
Provides GPU/Hardware stats via:
  1. REST API (primary) -- GET /bangtrix/hw/stats returns JSON
  2. WebSocket (fallback) -- /ws/hw_monitor for streaming

Also tries AMD temperature reader (wmic/PowerShell/thermal zone)
when backend returns 0 for temperature.
"""

import asyncio
import json
import logging
from collections import deque

logger = logging.getLogger(__name__)


class HardwareMonitorServer:
    """Thread-safe singleton providing GPU sensor data."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self.monitor = None
        self.history = deque(maxlen=60)
        self.running = False
        self._task = None

    def _get_monitor(self):
        if self.monitor is None:
            from monitor import get_universal_monitor
            self.monitor = get_universal_monitor()
        return self.monitor

    def _read_temp(self) -> tuple:
        """Try to read temperature from AMD temp reader as fallback."""
        try:
            from monitor.backends.amd_temp import read_amd_temperature
            return read_amd_temperature()
        except Exception:
            return 0.0, 0

    def get_stats_json(self, gpu_id: int = 0) -> dict:
        """Get GPU stats as a JSON-safe dict. Call from any thread."""
        try:
            monitor = self._get_monitor()
            if not monitor.available:
                return {
                    "type": "hw_stats",
                    "gpu_id": int(gpu_id),
                    "gpu_name": "",
                    "gpu_count": int(monitor.gpu_count),
                    "vendor": str(monitor.vendor),
                    "os_type": str(monitor.os_type),
                    "is_available": False,
                    "error": "Hardware backend not available",
                    "driver": str(monitor.driver),
                    "history": [],
                }

            stats = monitor.get_gpu_stats(gpu_id)
            util = round(float(stats.utilization_gpu or 0), 1)
            self.history.append(util)

            temp = round(float(stats.temperature or 0), 1)
            fan = int(stats.fan_speed or 0)

            # If PDH returned 0 temp, try AMD temp reader
            if temp == 0 or fan == 0:
                try:
                    at, af = self._read_temp()
                    if temp == 0 and at > 0:
                        temp = round(float(at), 1)
                    if fan == 0 and af > 0:
                        fan = int(af)
                except Exception:
                    pass

            return {
                "type": "hw_stats",
                "gpu_id": int(stats.gpu_id),
                "gpu_name": str(stats.gpu_name or f"GPU {gpu_id}"),
                "gpu_count": int(monitor.gpu_count),
                "vendor": str(stats.vendor or monitor.vendor),
                "os_type": str(monitor.os_type),
                "driver": str(stats.driver or monitor.driver or "unknown"),
                "is_apu": bool(stats.is_apu),
                "is_available": bool(stats.is_available),
                "gpu_utilization": util,
                "vram_usage_pct": round(float(stats.safe_memory_pct() or 0), 1),
                "vram_used_mb": int(round(stats.memory_used / (1024 * 1024), 0)) if stats.memory_used > 0 else 0,
                "vram_total_mb": int(round(stats.memory_total / (1024 * 1024), 0)) if stats.memory_total > 0 else 0,
                "vram_shared_mb": int(round(stats.memory_shared / (1024 * 1024), 0)) if stats.memory_shared > 0 else 0,
                "temperature": temp,
                "fan_speed": fan,
                "core_clock_mhz": int(stats.core_clock or 0),
                "power_draw_watts": round(float(stats.power_draw or 0), 1),
                "history": list(self.history),
            }
        except Exception as e:
            logger.error(f"HW Monitor: get_stats_json error: {e}")
            return {
                "type": "hw_stats",
                "gpu_id": int(gpu_id),
                "is_available": False,
                "error": str(e),
                "history": [],
            }


def get_hw_server() -> HardwareMonitorServer:
    """Get singleton instance."""
    return HardwareMonitorServer()