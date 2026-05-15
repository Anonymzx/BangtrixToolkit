"""
PowerShell Counter Backend
==========================
Reads GPU stats via Windows Performance Counters + WMI.
No extra dependencies (uses built-in PowerShell).
"""

import logging
import subprocess
import platform
import json
import re

from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)


class PowerShellBackend(MonitorBackend):
    name = "powershell-counters"

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            logger.debug("PS Backend: Windows only")
            return False
        return self._detect_gpus()

    def _detect_gpus(self) -> bool:
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
                self.available = self.gpu_count > 0
                if self.available:
                    logger.info(f"PS Backend: {self.gpu_count} GPU(s): {self.gpu_names}")
                return self.available
        except Exception as e:
            logger.debug(f"PS Backend detect error: {e}")
        return False

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}"

        gpu_util = self._get_gpu_utilization()
        temp = self._get_gpu_temperature()
        fan = self._get_gpu_fan_speed()

        # Get VRAM — try multiple methods
        mem_total, mem_used = self._get_vram_info()

        # Only fallback to system RAM if absolutely no GPU info
        if mem_total == 0:
            try:
                import psutil
                svmem = psutil.virtual_memory()
                mem_total = svmem.total
                mem_used = svmem.used
            except:
                pass

        mem_util = (mem_used / mem_total * 100) if mem_total > 0 else 0

        return AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=name,
            utilization_gpu=gpu_util,
            utilization_memory=mem_util,
            memory_total=mem_total,
            memory_used=mem_used,
            memory_free=mem_total - mem_used,
            temperature=temp,
            fan_speed=fan,
            is_available=True,
        )

    def _get_vram_info(self) -> tuple:
        """
        Get VRAM total & used in bytes.
        Tries multiple methods due to WMI AdapterRAM 4GB limit bug.
        """
        # Method 1: Direct registry query for accurate VRAM
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "$gpu = Get-WmiObject Win32_VideoController | Select-Object -First 1; "
                "[PSCustomObject]@{"
                "  Total = if ($gpu.AdapterRAM -and $gpu.AdapterRAM -gt 4GB) { $gpu.AdapterRAM } else { "
                "    # Try registry for accurate VRAM > 4GB\n"
                "    $paths = Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}\\*' "
                "-ErrorAction SilentlyContinue | Where-Object { $_.GetValue('HardwareInformation.AdapterString') -match 'Radeon|AMD' }; "
                "    foreach ($p in $paths) { "
                "      $vram = $p.GetValue('HardwareInformation.qwMemorySize'); "
                "      if ($vram -and $vram -gt 0) { $vram; break } "
                "    } "
                "  }; "
                "  Used = 0 "
                "} | ConvertTo-Json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                total = int(data.get('Total', 0))
                used = int(data.get('Used', 0))
                if total > 0:
                    return total, used
        except:
            pass

        # Method 2: Try reading registry directly via PowerShell
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "$paths = Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
                "{4d36e968-e325-11ce-bfc1-08002be10318}\\*' -ErrorAction SilentlyContinue; "
                "foreach ($p in $paths) { "
                "  $str = $p.GetValue('HardwareInformation.AdapterString'); "
                "  if ($str -match 'Radeon|AMD|RDNA') { "
                "    $mem = $p.GetValue('HardwareInformation.qwMemorySize'); "
                "    if ($mem) { $mem; break } "
                "  } "
                "}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                total = int(result.stdout.strip())
                if total > 0:
                    return total, 0
        except:
            pass

        # Method 3: AdapterRAM from WMI (may be capped at 4GB for some drivers)
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "(Get-WmiObject Win32_VideoController | Select-Object -First 1).AdapterRAM"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                total = int(result.stdout.strip())
                if total > 0:
                    return total, 0
        except:
            pass

        return 0, 0

    def _get_gpu_utilization(self) -> float:
        try:
            # Only query 3D engine type to avoid noise from other engines
            ps_cmd = (
                "@(Get-Counter '\\GPU Engine(*engtype_3D)\\*' -ErrorAction SilentlyContinue "
                "| Select-Object -ExpandProperty CounterSamples "
                "| Where-Object { $_.CookedValue -gt 0 }).CookedValue "
                "| Measure-Object -Average | Select-Object -ExpandProperty Average"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                # Counter returns nanoseconds per sample
                # Normalize: typical 60fps = 16.67ms per frame = 16,670,000 ns
                # 100% utilization on a single engine ≈ 16,670,000 ns
                # Multiple GPUs/engines sum — cap at 100
                pct = (val / 16670000.0) * 100.0
                return min(100.0, max(0.0, pct))
        except:
            pass
        return 0.0

    def _get_gpu_temperature(self) -> float:
        for ns in ['root/LibreHardwareMonitor', 'root/OpenHardwareMonitor']:
            try:
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    f"Get-WmiObject -Namespace '{ns}' -Class Sensor 2>$null | "
                    f"Where-Object {{ $_.SensorType -eq 'Temperature' -and "
                    f"$_.Name -match 'GPU' }} | Select-Object -First 1 -ExpandProperty Value"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0 and result.stdout.strip():
                    val = float(result.stdout.strip())
                    if val > 0:
                        return val
            except:
                pass
        return 0.0

    def _get_gpu_fan_speed(self) -> int:
        for ns in ['root/LibreHardwareMonitor', 'root/OpenHardwareMonitor']:
            try:
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    f"Get-WmiObject -Namespace '{ns}' -Class Sensor 2>$null | "
                    f"Where-Object {{ $_.SensorType -eq 'Fan' -and "
                    f"$_.Name -match 'GPU' }} | Select-Object -First 1 -ExpandProperty Value"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0 and result.stdout.strip():
                    val = float(result.stdout.strip())
                    if val > 0:
                        return int(val)
            except:
                pass
        return 0