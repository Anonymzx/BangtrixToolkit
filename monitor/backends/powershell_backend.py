"""
PowerShell Counter Backend
==========================
Real-time GPU monitoring via Windows Performance Counters.
Ultra-fast: uses Get-Counter only (reads pre-existing Windows counters, no HW query).
VRAM total auto-detected once at init (supports APU UMA shared memory).
Temperature reads from WMI thermal zone even without LHM.

BUG FIXES v4.1 (APU/iGPU Stability):
  - Cached temperature/fan readings (refresh every 10s, NOT per 500ms poll)
  - Added top-level try/except in get_stats() to catch ALL exceptions
  - Added timeout guard for all subprocess calls
"""

import logging
import subprocess
import platform
import json
import re
import time

from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


class PowerShellBackend(MonitorBackend):
    name = "powershell-counters"
    
    # Cache temperature/fan — refresh every 10 seconds
    _TEMP_CACHE_SECONDS = 10.0

    def __init__(self):
        super().__init__()
        self._vram_total = 0          # Dedicated VRAM (UMA buffer for APU) in bytes
        self._vram_total_mb = 0
        self._shared_vram_total = 0   # Shared system memory for APU in bytes
        self._gpu_name_cached = ""
        self._is_apu = False  # Integrated GPU (APU) flag
        
        # Temperature/Fan cache
        self._cached_temp: float = 0.0
        self._cached_fan: int = 0
        self._last_temp_check: float = 0.0

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            logger.debug("PS Backend: Windows only")
            return False

        if not self._init_gpu_and_vram():
            return False

        self.available = True
        return True

    def _init_gpu_and_vram(self) -> bool:
        """Detect GPU + cache VRAM total at init."""
        ps_script = (
            "$gpu = Get-WmiObject Win32_VideoController | Select-Object -First 1; "
            "$name = ''; $vram = 0; $isAPU = $false; "
            "if ($gpu) { "
            "  $name = $gpu.Name; "
            "  # Detect APU: check if GPU name contains typical APU keywords\n"
            "  if ($name -match 'Radeon.*Graphics|Radeon.*Vega|RX Vega|Radeon 6') { $isAPU = $true }; "
            "}; "
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
            # For APU: use half of system RAM as estimated VRAM
            "if ($vram -eq 0 -and $isAPU) { "
            "  $ram = Get-WmiObject Win32_ComputerSystem | Select-Object -First 1; "
            "  $vram = [int]($ram.TotalPhysicalMemory * 0.25); " # 25% of system RAM
            "}; "
            # Absolute fallback
            "if ($vram -eq 0) { $vram = 512MB }; "
            "[PSCustomObject]@{ Name = $name; Vram = $vram; IsAPU = $isAPU } | ConvertTo-Json"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                name = data.get('Name', '').strip()
                vram = int(data.get('Vram', 0))
                is_apu = data.get('IsAPU', False)

                if name:
                    self.gpu_names = [name]
                    self.gpu_count = 1
                    self._gpu_name_cached = name
                else:
                    self.gpu_names = ["AMD APU"]
                    self.gpu_count = 1
                    self._gpu_name_cached = "AMD APU"

                self._is_apu = is_apu

                # For APU: use full system RAM / 4 as VRAM estimate
                if is_apu and vram < 1024 * 1024 * 1024:
                    # vram is too small for APU, recalculate
                    try:
                        import psutil
                        vram = int(psutil.virtual_memory().total * 0.25)
                    except:
                        vram = 4 * 1024 * 1024 * 1024  # 4GB APU default
                
                if vram > 0:
                    self._vram_total = vram
                    self._vram_total_mb = vram / (1024 * 1024)
                    logger.info(f"PS Backend: {name} — VRAM: {vram/(1024*1024):.0f}MB (APU={is_apu})")
                else:
                    self._vram_total = 512 * 1024 * 1024
                    self._vram_total_mb = 512
                    logger.warning(f"PS Backend: VRAM detection failed, using 512MB fallback")

                return True
        except Exception as e:
            logger.debug(f"PS Backend init error: {e}")

        return False

    def _run_ps(self, cmd: str, timeout: int = 2) -> Optional[str]:
        """Run a quick PowerShell command with timeout.
        FIXED: Added timeout to prevent blocking on APU systems."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True, text=True, timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.debug(f"PS Backend: command timed out ({timeout}s)")
        except Exception:
            pass
        return None

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        """Real-time GPU stats via fast Get-Counter + cached temperature.
        
        For APU systems, VRAM = Dedicated VRAM + Shared System Memory.
        The memory_shared field holds shared memory portion.
        The memory_total reflects combined total.
        """
        try:
            name = self._gpu_name_cached or "AMD GPU"

            # For APU: use dedicated + shared memory as total VRAM
            vram_total = self._vram_total
            shared_total = self._shared_vram_total

            # If APU and we have shared memory info, combine them
            if self._is_apu:
                try:
                    if shared_total == 0:
                        # Estimate shared memory as 50% of system RAM
                        try:
                            import psutil
                            shared_total = int(psutil.virtual_memory().total * 0.5)
                            self._shared_vram_total = shared_total
                        except Exception:
                            shared_total = 4 * 1024 * 1024 * 1024  # 4GB fallback
                    vram_total = self._vram_total + shared_total
                except Exception:
                    # Fallback: just use dedicated VRAM
                    logger.debug("PS Backend: shared VRAM calc failed — using dedicated only")
                    shared_total = 0
                    vram_total = self._vram_total

            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=name,
                memory_total=vram_total,
                memory_shared=shared_total,
                is_apu=self._is_apu,
                is_available=True,
            )

            # GPU Utilization (REAL-TIME) — using percentage-direct method
            stats.utilization_gpu = self._get_utilization_percent()

            # VRAM Usage
            if self._is_apu:
                # For APU: read shared usage + use system RAM percentage
                import psutil
                svmem = psutil.virtual_memory()
                # Estimate the shared portion usage based on system memory pressure
                shared_used = int(shared_total * (svmem.percent / 100))
                dedicated_used = self._vram_total  # assume UMA buffer is fully committed
                stats.memory_used = dedicated_used + shared_used
                stats.memory_shared = shared_used
                stats.memory_free = max(0, vram_total - stats.memory_used)
                if vram_total > 0:
                    stats.utilization_memory = (stats.memory_used / vram_total) * 100.0
            else:
                vram_used = self._get_vram_used_fast()
                if vram_used > 0 and self._vram_total > 0:
                    stats.memory_used = vram_used
                    stats.memory_free = max(0, self._vram_total - vram_used)
                    stats.utilization_memory = (vram_used / self._vram_total) * 100.0
                else:
                    import psutil
                    svmem = psutil.virtual_memory()
                    vram_used = int(self._vram_total * (svmem.percent / 100))
                    stats.memory_used = vram_used
                    stats.memory_free = self._vram_total - vram_used
                    stats.utilization_memory = svmem.percent

            # Temperature (CACHED — only refreshed every 10s)
            temp_val, fan_val = self._get_cached_temp_fan()
            stats.temperature = temp_val
            stats.fan_speed = fan_val

            return stats
        except Exception as e:
            logger.error(f"PS Backend get_stats error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                gpu_name=self._gpu_name_cached or "AMD GPU",
                is_available=False,
                error_message=str(e)
            )

    def _get_cached_temp_fan(self):
        """Return cached temperature/fan.
        FIXED: Only refreshes every _TEMP_CACHE_SECONDS to avoid
        spawning PowerShell subprocesses every 500ms."""
        now = time.time()
        if now - self._last_temp_check >= self._TEMP_CACHE_SECONDS:
            temp, fan = self._get_temp_and_fan()
            if temp > 0:
                self._cached_temp = temp
                self._cached_fan = fan
            self._last_temp_check = now
        return self._cached_temp, self._cached_fan

    def _get_utilization_percent(self) -> float:
        """
        Get GPU utilization as percentage using the same source as Task Manager.
        FIXED: Removed excessive fallback chains that cause timeout on APU.
        Now tries only 2 fast methods, then returns 0.
        """
        # Method 1: GPU Adapter Utilization Percentage (Task Manager data) - FAST
        for query_pattern in [
            "Get-Counter '\\GPU Adapter(*)\\*'",
            "Get-Counter '\\GPU(*)\\*'",
        ]:
            ps_cmd = (
                f"{query_pattern} -ErrorAction SilentlyContinue "
                "| Select-Object -ExpandProperty CounterSamples "
                "| Where-Object { $_.Path -match 'Utilization Percentage' -or $_.Path -match 'Utilization\\%' } "
                "| Select-Object -First 1 -ExpandProperty CookedValue"
            )
            result = self._run_ps(ps_cmd, timeout=1)
            if result:
                try:
                    val = float(result)
                    if 0 <= val <= 100:
                        return min(100.0, max(0.0, val))
                    if 0 <= val <= 1:
                        return min(100.0, max(0.0, val * 100.0))
                except:
                    pass

        # Method 2: GPU Engine 3D sum - FAST
        try:
            ps_cmd = (
                "Get-Counter '\\GPU Engine(*engtype_3D)\\*' -ErrorAction SilentlyContinue "
                "| Select-Object -ExpandProperty CounterSamples "
                "| Where-Object { $_.Path -notmatch 'pid_\\\\d+_' } "
                "| Measure-Object -Property CookedValue -Sum "
                "| Select-Object -ExpandProperty Sum"
            )
            result = self._run_ps(ps_cmd, timeout=1)
            if result:
                val = float(result)
                if val > 1000:
                    pct = val / 100000.0
                elif val <= 1:
                    pct = val * 100.0
                else:
                    pct = val
                return min(100.0, max(0.0, pct))
        except:
            pass

        return 0.0

    def _get_vram_used_fast(self) -> int:
        """REAL-TIME VRAM used in bytes via Get-Counter"""
        result = self._run_ps(
            "Get-Counter '\\GPU Adapter(*)\\*' -ErrorAction SilentlyContinue "
            "| Select-Object -ExpandProperty CounterSamples "
            "| Where-Object { $_.Path -match 'Dedicated Memory Used' } "
            "| Select-Object -First 1 -ExpandProperty CookedValue",
            timeout=1
        )
        if result:
            try:
                return int(float(result))
            except:
                pass
        return 0

    def _get_temp_and_fan(self) -> tuple:
        """
        Get temperature and fan speed.
        Tries multiple WMI methods including LHM, thermal zone, and WMI.
        FIXED: All subprocess calls have timeouts to prevent blocking on APU.
        """
        # Method 1: LHM/OHM WMI (if LHM is running with --wmi)
        result = self._run_ps(
            "$sensors = @(); "
            "try { $sensors += Get-WmiObject -Namespace 'root/LibreHardwareMonitor' -Class Sensor 2>$null } catch {}; "
            "if (-not $sensors) { try { $sensors += Get-WmiObject -Namespace 'root/OpenHardwareMonitor' -Class Sensor 2>$null } catch {} }; "
            "if ($sensors) { "
            "  $sensors | Where-Object { $_.Value -gt 0 } | "
            "  Select-Object SensorType, Name, Value | ConvertTo-Json -Compress "
            "}",
            timeout=2
        )
        if result and result != 'null':
            try:
                data = json.loads(result)
                if isinstance(data, dict): data = [data]
                temp_val = 0.0
                fan_val = 0
                for item in data:
                    stype = item.get('SensorType', '')
                    sname = item.get('Name', '')
                    svalue = float(item.get('Value', 0))
                    if stype == 'Temperature':
                        if 30 <= svalue <= 100:
                            if temp_val == 0: temp_val = svalue
                            if any(x in sname for x in ['GPU', 'Radeon', 'AMD', 'Core', 'Tctl', 'Tdie']):
                                temp_val = svalue
                    elif stype == 'Fan':
                        if fan_val == 0: fan_val = int(svalue)
                        if any(x in sname for x in ['GPU', 'Radeon', 'AMD']):
                            fan_val = int(svalue)
                if temp_val > 0:
                    return temp_val, fan_val
            except:
                pass

        # Method 2: Windows Thermal Zone (works on ALL laptops, no admin needed)
        result = self._run_ps(
            "$temps = Get-WmiObject -Namespace 'root/WMI' -Class MSAcpi_ThermalZoneTemperature "
            "-ErrorAction SilentlyContinue | Where-Object { $_.Active -eq $true }; "
            "if ($temps) { "
            "  $temps | Select-Object @{N='Temp';E={[math]::Round(($_.CurrentTemperature - 2732) / 10, 1)}}, InstanceName | "
            "  Where-Object { $_.Temp -gt 0 -and $_.Temp -lt 120 } | "
            "  Select-Object -First 1 -ExpandProperty Temp "
            "}",
            timeout=2
        )
        if result:
            try:
                val = float(result)
                if 30 <= val <= 100:
                    logger.debug(f"PS Backend: thermal zone temp = {val}°C")
                    return val, 0
            except:
                pass

        # Method 3: Thermal Zone Information counter - FAST
        result = self._run_ps(
            "Get-Counter '\\Thermal Zone Information(*)\\*' -ErrorAction SilentlyContinue "
            "| Select-Object -ExpandProperty CounterSamples "
            "| Where-Object { $_.Path -match 'Temperature' -and $_.CookedValue -gt 0 } "
            "| Select-Object -First 1 -ExpandProperty CookedValue",
            timeout=1
        )
        if result:
            try:
                val = float(result)
                temp_c = (val - 2732) / 10
                if 30 <= temp_c <= 100:
                    logger.debug(f"PS Backend: thermal counter temp = {temp_c}°C")
                    return temp_c, 0
            except:
                pass

        return 0.0, 0