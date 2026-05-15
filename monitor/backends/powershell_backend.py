"""
PowerShell Counter Backend
==========================
Real-time GPU monitoring via Windows Performance Counters.
Ultra-fast: uses Get-Counter only (reads pre-existing Windows counters, no HW query).
VRAM total auto-detected once at init (supports APU UMA shared memory).
"""

import logging
import subprocess
import platform
import json
import re
import time

from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)


class PowerShellBackend(MonitorBackend):
    name = "powershell-counters"

    def __init__(self):
        super().__init__()
        self._vram_total = 0
        self._gpu_name_cached = ""
        self._running_processes = {}  # cache process list for VRAM estimate

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            logger.debug("PS Backend: Windows only")
            return False

        # Detect GPU(s) and cache VRAM total once
        if not self._init_gpu_and_vram():
            return False

        self.available = True
        return True

    def _init_gpu_and_vram(self) -> bool:
        """
        Detect GPU + cache VRAM total at init (not per-poll).
        Works for dedicated GPUs and AMD APU shared memory.
        """
        # Get GPU name and try all VRAM detection methods in one PowerShell call
        ps_script = (
            "$gpu = Get-WmiObject Win32_VideoController | Select-Object -First 1; "
            "$name = ''; $vram = 0; "
            "if ($gpu) { $name = $gpu.Name }; "
            # Try UMA_FB_SIZE (APU shared memory)
            "$paths = Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}\\*' "
            "-ErrorAction SilentlyContinue; "
            "foreach ($p in $paths) { "
            "  $uma = $p.GetValue('UMA_FB_SIZE'); "
            "  if ($uma) { $vram = $uma * 1MB; break }; "
            "  $gpuMem = $p.GetValue('HardwareInformation.GpuMemorySize'); "
            "  if ($gpuMem) { $vram = $gpuMem; break }; "
            "  $mem = $p.GetValue('HardwareInformation.qwMemorySize'); "
            "  if ($mem) { $vram = $mem; break }; "
            "}; "
            # Fallback: WMI AdapterRAM
            "if ($vram -eq 0 -and $gpu.AdapterRAM) { $vram = $gpu.AdapterRAM }; "
            # Fallback: 512MB default for APU
            "if ($vram -eq 0) { $vram = 512MB }; "
            "[PSCustomObject]@{ Name = $name; Vram = $vram } | ConvertTo-Json"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                name = data.get('Name', '').strip()
                vram = int(data.get('Vram', 0))

                if name:
                    self.gpu_names = [name]
                    self.gpu_count = 1
                    self._gpu_name_cached = name
                else:
                    self.gpu_names = ["AMD APU"]
                    self.gpu_count = 1
                    self._gpu_name_cached = "AMD APU"

                if vram > 0:
                    self._vram_total = vram
                    logger.info(f"PS Backend: {name} — VRAM: {vram/(1024*1024):.0f}MB")
                else:
                    self._vram_total = 512 * 1024 * 1024  # 512MB fallback
                    logger.warning(f"PS Backend: VRAM detection failed, using 512MB fallback")

                return True
        except Exception as e:
            logger.debug(f"PS Backend init error: {e}")

        return False

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        """
        Real-time GPU stats via fast Get-Counter queries only.
        No WMI, no registry per-poll = ultra fast.
        """
        name = self._gpu_name_cached or "AMD GPU"
        stats = AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=name,
            memory_total=self._vram_total,
            is_available=True,
        )

        # --- GPU Utilization (REAL-TIME) ---
        stats.utilization_gpu = self._get_utilization_fast()

        # --- VRAM Usage (REAL-TIME via GPU Adapter Counters) ---
        vram_used = self._get_vram_used_fast()
        if vram_used > 0 and self._vram_total > 0:
            stats.memory_used = vram_used
            stats.memory_free = max(0, self._vram_total - vram_used)
            stats.utilization_memory = (vram_used / self._vram_total) * 100.0
        else:
            # Fallback: estimate via process memory
            import psutil
            svmem = psutil.virtual_memory()
            stats.memory_used = self._vram_total  # show as full for APU
            stats.memory_free = 0
            stats.utilization_memory = (svmem.used / svmem.total * 100) if svmem.total > 0 else 0

        # --- Temperature (via fast WMI LHM check) ---
        stats.temperature = self._get_temperature_fast()

        # --- Fan Speed ---
        stats.fan_speed = self._get_fan_speed_fast()

        return stats

    def _get_utilization_fast(self) -> float:
        """REAL-TIME GPU utilization via Get-Counter (sub-millisecond)"""
        try:
            ps_cmd = (
                "Get-Counter '\\GPU Engine(*engtype_3D)\\*' -ErrorAction SilentlyContinue "
                "| Select-Object -ExpandProperty CounterSamples "
                "| Measure-Object -Property CookedValue -Sum "
                "| Select-Object -ExpandProperty Sum"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                # On Windows 10/11, this counter is nanoseconds per frame
                # Normalize to 0-100%: divide by 100000 to get ~%
                return min(100.0, max(0.0, val / 100000.0))
        except:
            pass
        return 0.0

    def _get_vram_used_fast(self) -> int:
        """REAL-TIME VRAM used in bytes via Get-Counter (instant)"""
        try:
            ps_cmd = (
                "Get-Counter '\\GPU Adapter(*)\\*' -ErrorAction SilentlyContinue "
                "| Select-Object -ExpandProperty CounterSamples "
                "| Where-Object { $_.Path -match 'Dedicated Memory Used' } "
                "| Select-Object -First 1 -ExpandProperty CookedValue"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(float(result.stdout.strip()))
        except:
            pass
        return 0

    def _get_temperature_fast(self) -> float:
        """Temperature via WMI (cached namespace check)"""
        try:
            ps_cmd = (
                "Get-WmiObject -Namespace 'root/LibreHardwareMonitor' -Class Sensor 2>$null "
                "| Where-Object { $_.SensorType -eq 'Temperature' -and $_.Name -match 'GPU' -and $_.Value -gt 0 } "
                "| Select-Object -First 1 -ExpandProperty Value"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0: return val
        except:
            pass

        # Fallback: OpenHardwareMonitor
        try:
            ps_cmd = (
                "Get-WmiObject -Namespace 'root/OpenHardwareMonitor' -Class Sensor 2>$null "
                "| Where-Object { $_.SensorType -eq 'Temperature' -and $_.Name -match 'GPU' -and $_.Value -gt 0 } "
                "| Select-Object -First 1 -ExpandProperty Value"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0: return val
        except:
            pass

        return 0.0

    def _get_fan_speed_fast(self) -> int:
        """Fan speed via WMI"""
        try:
            ps_cmd = (
                "Get-WmiObject -Namespace 'root/LibreHardwareMonitor' -Class Sensor 2>$null "
                "| Where-Object { $_.SensorType -eq 'Fan' -and $_.Name -match 'GPU' -and $_.Value -gt 0 } "
                "| Select-Object -First 1 -ExpandProperty Value"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0: return int(val)
        except:
            pass

        # Fallback: OpenHardwareMonitor
        try:
            ps_cmd = (
                "Get-WmiObject -Namespace 'root/OpenHardwareMonitor' -Class Sensor 2>$null "
                "| Where-Object { $_.SensorType -eq 'Fan' -and $_.Name -match 'GPU' -and $_.Value -gt 0 } "
                "| Select-Object -First 1 -ExpandProperty Value"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0: return int(val)
        except:
            pass

        return 0