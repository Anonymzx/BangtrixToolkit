"""
GPU Performance Counters via PowerShell
========================================
Windows-only: reads GPU utilization, VRAM usage, and temperature
via built-in performance counters and WMI.
No dependencies required beyond built-in Python + PowerShell.
"""

import subprocess
import logging
import platform
import json
import re

logger = logging.getLogger(__name__)


class GPUCounterMonitor:
    """Monitor GPU metrics via PowerShell performance counters and WMI"""

    def __init__(self):
        self.available = False
        self.gpu_count = 0
        self.gpu_names = []
        self.method = "powershell-counters"
        self._detect()

    def _detect(self):
        """Detect GPU availability via WMI"""
        if platform.system() != "Windows":
            return

        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject Win32_VideoController | "
                "Where-Object { $_.AdapterRAM -gt 0 } | "
                "Select-Object Name, AdapterRAM | ConvertTo-Json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for gpu in data:
                    name = gpu.get('Name', 'Unknown GPU').strip()
                    self.gpu_names.append(name)
                self.gpu_count = len(self.gpu_names)
                if self.gpu_count > 0:
                    self.available = True
                    logger.info(f"GPU Counters: {self.gpu_count} GPU(s): {self.gpu_names}")
                    return
        except Exception as e:
            logger.debug(f"GPU detection error: {e}")

    def get_gpu_utilization(self, gpu_id: int = 0) -> float:
        """Get GPU utilization % via performance counters"""
        try:
            # Get average 3D engine usage
            ps_cmd = (
                "Get-Counter '\\GPU Engine(*engtype_3D)\\*' -SampleInterval 0 -MaxSamples 1 "
                "2>$null | Select-Object -ExpandProperty CounterSamples | "
                "Measure-Object -Property CookedValue -Average | "
                "Select-Object -ExpandProperty Average"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0:
                    return val
        except Exception as e:
            logger.debug(f"GPU utilization error: {e}")
        return 0.0

    def _detect_hardware_monitors(self):
        """Detect which hardware monitoring tools are installed"""
        monitors = []

        # LibreHardwareMonitor / OpenHardwareMonitor WMI namespace
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject -Namespace 'root/LibreHardwareMonitor' -Class Sensor 2>$null | "
                "Select-Object -First 1 | ConvertTo-Json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != 'null':
                monitors.append("LibreHardwareMonitor")
        except:
            pass

        if 'LibreHardwareMonitor' not in monitors:
            try:
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    "Get-WmiObject -Namespace 'root/OpenHardwareMonitor' -Class Sensor 2>$null | "
                    "Select-Object -First 1 | ConvertTo-Json"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != 'null':
                    monitors.append("OpenHardwareMonitor")
            except:
                pass

        # MSI Afterburner shared memory
        try:
            import ctypes
            try:
                # Try to open the shared memory file
                import ctypes.wintypes
                handle = ctypes.windll.kernel32.OpenFileMappingW(
                    0x0001, False, "MSE_Afterburner_SharedMemory"
                )
                if handle:
                    monitors.append("MSIAfterburner")
                    ctypes.windll.kernel32.CloseHandle(handle)
            except:
                pass
        except:
            pass

        self._hw_monitors = monitors
        if monitors:
            logger.info(f"GPU Counters: Detected HW monitors: {monitors}")
        return monitors

    def get_gpu_temperature(self, gpu_id: int = 0) -> float:
        """Get GPU temperature via LibreHardwareMonitor, OpenHardwareMonitor, or other tools"""
        # Try LibreHardwareMonitor first (if installed)
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject -Namespace 'root/LibreHardwareMonitor' -Class Sensor "
                "2>$null | Where-Object { $_.SensorType -eq 'Temperature' -and "
                "$_.Name -match 'GPU' } | Select-Object -First 1 -ExpandProperty Value"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0:
                    return val
        except:
            pass

        # Try OpenHardwareMonitor
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject -Namespace 'root/OpenHardwareMonitor' -Class Sensor "
                "2>$null | Where-Object { $_.SensorType -eq 'Temperature' -and "
                "$_.Name -match 'GPU' } | Select-Object -First 1 -ExpandProperty Value"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0:
                    return val
        except:
            pass

        return 0.0

    def get_fan_speed(self, gpu_id: int = 0) -> int:
        """Get fan speed from hardware monitors"""
        # LibreHardwareMonitor
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject -Namespace 'root/LibreHardwareMonitor' -Class Sensor "
                "2>$null | Where-Object { $_.SensorType -eq 'Fan' -and "
                "$_.Name -match 'GPU' } | Select-Object -First 1 -ExpandProperty Value"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0:
                    return int(val)
        except:
            pass

        # OpenHardwareMonitor
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject -Namespace 'root/OpenHardwareMonitor' -Class Sensor "
                "2>$null | Where-Object { $_.SensorType -eq 'Fan' -and "
                "$_.Name -match 'GPU' } | Select-Object -First 1 -ExpandProperty Value"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0:
                    return int(val)
        except:
            pass

        return 0

    def get_gpu_vram_mb(self, gpu_id: int = 0) -> dict:
        """Get VRAM info from WMI"""
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "(Get-WmiObject Win32_VideoController | Select-Object -First 1).AdapterRAM"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip():
                total_bytes = int(result.stdout.strip())
                total_mb = total_bytes / (1024 * 1024)
                # We can't get actual VRAM usage without ADLX/ADL
                # Estimate via process memory if needed
                return {'total_mb': total_mb, 'used_mb': 0, 'free_mb': total_mb}
        except:
            pass
        return {'total_mb': 0, 'used_mb': 0, 'free_mb': 0}

    def get_all_metrics(self, gpu_id: int = 0) -> dict:
        """Get all metrics for a GPU in one call"""
        return {
            'utilization': self.get_gpu_utilization(gpu_id),
            'temperature': self.get_gpu_temperature(gpu_id),
            'vram': self.get_gpu_vram_mb(gpu_id),
            'fan_speed': self.get_fan_speed(gpu_id),
            'gpu_name': self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"GPU {gpu_id}",
        }


# Singleton
_gpu_counter = None


def get_gpu_counter() -> GPUCounterMonitor:
    global _gpu_counter
    if _gpu_counter is None:
        _gpu_counter = GPUCounterMonitor()
    return _gpu_counter


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    mon = get_gpu_counter()
    if mon.available:
        print(f"GPU Counters: {mon.gpu_count} GPU(s)")
        for i, name in enumerate(mon.gpu_names):
            print(f"\n  GPU {i}: {name}")
            metrics = mon.get_all_metrics(i)
            print(f"    Utilization: {metrics['utilization']:.1f}%")
            print(f"    Temperature: {metrics['temperature']:.1f}°C")
            print(f"    VRAM: {metrics['vram']['total_mb']:.0f} MB total")
            print(f"    Fan: {metrics['fan_speed']}%")
    else:
        print("GPU Counters: Not available")