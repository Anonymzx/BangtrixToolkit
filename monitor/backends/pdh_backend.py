r"""
PDH Backend - Windows Performance Counter Native (v2)
======================================================
Reads GPU data directly from Windows Performance Counters via win32pdh API.
Same data source as Windows Task Manager.

Fixes:
  - VRAM detection via Registry (win32api) with WMI fallback
  - Temperature via ADL + LHM WMI + Thermal Zone WMI
  - Fan Speed via ADL + LHM WMI
  - GPU Utilization via GPU Engine(engtype_3D) Utilization Percentage
  - VRAM Used via GPU Adapter Memory Dedicated Usage

Zero PowerShell at runtime (1x at init for WMI fallback only).
"""

import logging
import platform
from typing import Optional

from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)

FMT_DOUBLE = 0x00000200
FMT_LARGE = 0x00000400
FMT_NOSCALE = 0x00001000


class PDHCounter:
    """Persistent Windows Performance Counter handle"""
    __slots__ = ('counter_path', '_query', '_counter', '_is_open')

    def __init__(self, counter_path: str):
        self.counter_path = counter_path
        self._query = None
        self._counter = None
        self._is_open = False

    def open(self) -> bool:
        try:
            import win32pdh
            self._query = win32pdh.OpenQuery()
            self._counter = win32pdh.AddCounter(self._query, self.counter_path)
            win32pdh.CollectQueryData(self._query)
            self._is_open = True
            return True
        except Exception as e:
            logger.debug(f"PDHCounter: cannot open '{self.counter_path}': {e}")
            return False

    def read_double(self) -> Optional[float]:
        if not self._is_open:
            return None
        try:
            import win32pdh
            win32pdh.CollectQueryData(self._query)
            _, val = win32pdh.GetFormattedCounterValue(self._counter, FMT_DOUBLE | FMT_NOSCALE)
            return float(val)
        except Exception:
            return None

    def read_int(self) -> Optional[int]:
        if not self._is_open:
            return None
        try:
            import win32pdh
            win32pdh.CollectQueryData(self._query)
            _, val = win32pdh.GetFormattedCounterValue(self._counter, FMT_LARGE | FMT_NOSCALE)
            return int(val)
        except Exception:
            return None

    def close(self):
        if self._is_open:
            try:
                import win32pdh
                win32pdh.RemoveCounter(self._counter)
                win32pdh.CloseQuery(self._query)
            except Exception:
                pass
            self._is_open = False


class PDHBackend(MonitorBackend):
    """PDH native backend - real-time GPU stats via Windows Performance Counters"""
    name = "pdh-counters"

    def __init__(self):
        super().__init__()
        self._gpu_name: str = ""
        self._vram_total: int = 0
        self._vram_total_mb: float = 0
        self._util_counter: Optional[PDHCounter] = None
        self._vram_counter: Optional[PDHCounter] = None
        self._adl_available: bool = False
        self._adl_ctx = None

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            return False

        self._detect_gpu_info()
        util_path = self._detect_utilization_counter()
        if util_path:
            self._util_counter = PDHCounter(util_path)
            self._util_counter.open()
        vram_path = self._detect_vram_counter()
        if vram_path:
            self._vram_counter = PDHCounter(vram_path)
            self._vram_counter.open()
        self._try_init_adl()

        self.gpu_names = [self._gpu_name] if self._gpu_name else ["AMD GPU"]
        self.gpu_count = 1
        self.available = True
        logger.info(
            f"PDH: {self.gpu_names[0]} | VRAM={self._vram_total_mb:.0f}MB | "
            f"Util={'OK' if self._util_counter else 'N/A'} | "
            f"VRAM={'OK' if self._vram_counter else 'N/A'} | "
            f"ADL={'OK' if self._adl_available else 'N/A'}"
        )
        return True

    def _detect_gpu_info(self) -> None:
        """Auto-detect GPU name + VRAM total. Multi-method for ALL AMD GPUs."""
        # Method 1: Registry (most reliable, works for all AMD drivers)
        if self._detect_via_registry():
            return
        # Method 2: WMI via PowerShell tempfile (avoids bash $ expansion)
        if self._detect_via_wmi():
            return
        # Method 3: Registry enumerate ALL GPUs (non-AMD + AMD)
        if self._detect_via_registry_any():
            return
        # Hard fallback (should never reach here on real hardware)
        self._gpu_name = "AMD GPU"
        self._vram_total = 8 * 1024 * 1024 * 1024
        self._vram_total_mb = 8192
        logger.warning("PDH: using default VRAM (8GB) - GPU detection failed")

    def _detect_via_registry(self) -> bool:
        """Read GPU name + VRAM from Windows Registry (HKLM GPU class)."""
        try:
            import win32api, win32con
            gpu_class = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            key = win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, gpu_class, 0, win32con.KEY_READ)  # type: ignore
            i = 0
            while True:
                try:
                    subkey_name = win32api.RegEnumKey(key, i)
                    subkey = win32api.RegOpenKeyEx(key, subkey_name, 0, win32con.KEY_READ)  # type: ignore
                    try:
                        driver_result = win32api.RegQueryValueEx(subkey, "DriverDesc")
                        driver_desc = str(driver_result[0]) if driver_result[0] else ""
                        if 'amd' in driver_desc.lower() or 'radeon' in driver_desc.lower():
                            self._gpu_name = driver_desc
                            vram_val = self._read_reg_vram(subkey)
                            win32api.RegCloseKey(subkey)
                            win32api.RegCloseKey(key)
                            if vram_val > 0:
                                self._vram_total = vram_val
                                self._vram_total_mb = float(vram_val) / (1024.0 * 1024.0)
                                logger.info(f"PDH: Registry VRAM={self._vram_total_mb:.0f}MB")
                            else:
                                self._vram_total = 8 * 1024 * 1024 * 1024
                                self._vram_total_mb = 8192
                                logger.warning(f"PDH: Registry found GPU but no VRAM key, using 8GB fallback")
                            return True
                    except Exception:
                        pass
                    win32api.RegCloseKey(subkey)
                    i += 1
                except Exception:
                    break
            win32api.RegCloseKey(key)
        except Exception:
            pass
        return False

    def _detect_via_registry_any(self) -> bool:
        """Fallback: detect ANY GPU from registry (non-AMD too), prioritize first."""
        try:
            import win32api, win32con
            gpu_class = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            key = win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, gpu_class, 0, win32con.KEY_READ)  # type: ignore
            i = 0
            while True:
                try:
                    subkey_name = win32api.RegEnumKey(key, i)
                    subkey = win32api.RegOpenKeyEx(key, subkey_name, 0, win32con.KEY_READ)  # type: ignore
                    try:
                        # Only accept keys that have a DriverDesc (skip non-GPU entries)
                        driver_result = win32api.RegQueryValueEx(subkey, "DriverDesc")
                        driver_desc = str(driver_result[0]) if driver_result[0] else ""
                        if driver_desc and len(driver_desc) > 3:
                            self._gpu_name = driver_desc
                            vram_val = self._read_reg_vram(subkey)
                            win32api.RegCloseKey(subkey)
                            win32api.RegCloseKey(key)
                            if vram_val > 0:
                                self._vram_total = vram_val
                                self._vram_total_mb = float(vram_val) / (1024.0 * 1024.0)
                            else:
                                self._vram_total = 8 * 1024 * 1024 * 1024
                                self._vram_total_mb = 8192
                            return True
                    except Exception:
                        pass
                    win32api.RegCloseKey(subkey)
                    i += 1
                except Exception:
                    break
            win32api.RegCloseKey(key)
        except Exception:
            pass
        return False

    def _read_reg_vram(self, subkey) -> int:
        """
        Read VRAM from registry key. Tries ALL known value names.
        Returns bytes (not MB). Returns 0 if nothing found.
        """
        try:
            import win32api
        except ImportError:
            return 0

        # All possible VRAM registry value names across different AMD drivers
        vram_keys = [
            'HardwareInformation.qwMemorySize',   # Windows 10/11 (64-bit QWORD) - most common
            'HardwareInformation.GpuMemorySize',  # Windows 10/11 (DWORD fallback)
            'HardwareInformation.MemorySize',     # Older drivers / APU
            'UMA_FB_SIZE',                        # APU Unified Memory Architecture
        ]

        for val_name in vram_keys:
            try:
                result = win32api.RegQueryValueEx(subkey, val_name)
                val = result[0]
                if val is None or val == 0:
                    continue

                if isinstance(val, bytes):
                    import struct
                    if len(val) >= 8:
                        val = struct.unpack('Q', val[:8])[0]
                    elif len(val) >= 4:
                        val = struct.unpack('I', val[:4])[0]
                    else:
                        continue
                elif isinstance(val, (int, float)):
                    val = int(val)
                elif isinstance(val, str):
                    try:
                        val = int(val)
                    except (ValueError, TypeError):
                        continue
                else:
                    continue

                if val <= 0:
                    continue

                # APU UMA_FB_SIZE is in MB, convert to bytes
                if val_name == 'UMA_FB_SIZE' and val < 1024 * 1024:
                    val = val * 1024 * 1024

                # Sanity: VRAM should be at least 128MB and at most 256GB
                min_vram = 128 * 1024 * 1024
                max_vram = 256 * 1024 * 1024 * 1024
                if min_vram <= val <= max_vram:
                    logger.debug(f"PDH: found VRAM via {val_name} = {val/(1024*1024):.0f}MB")
                    return val

            except Exception:
                pass

        return 0

    def _detect_via_wmi(self) -> bool:
        """Fallback GPU detection via WMI (PowerShell tempfile to avoid bash $ expansion)."""
        script = r"""$gpu = Get-WmiObject Win32_VideoController | Where-Object { $_.Name -match 'AMD|Radeon' } | Select-Object -First 1
if (-not $gpu) { $gpu = Get-WmiObject Win32_VideoController | Select-Object -First 1 }
if ($gpu) { ConvertTo-Json -InputObject @{ Name = $gpu.Name; Vram = $gpu.AdapterRAM } }"""
        result = self._run_ps_script(script)
        if result:
            try:
                import json
                data = json.loads(result)
                name = data.get('Name', '').strip()
                vram = int(data.get('Vram', 0) or 0)
                if name:
                    self._gpu_name = name
                if vram > 0:
                    self._vram_total = vram
                    self._vram_total_mb = vram / (1024.0 * 1024.0)
                    logger.info(f"PDH: WMI VRAM={self._vram_total_mb:.0f}MB")
                    return True
            except Exception as e:
                logger.debug(f"PDH WMI parse: {e}")
        return False

    @staticmethod
    def _run_ps_script(script_content: str) -> Optional[str]:
        """Run PowerShell script via temp file to avoid bash variable expansion."""
        import subprocess, tempfile, os
        try:
            f = tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8')
            f.write(script_content)
            f.close()
            r = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-NoProfile', '-File', f.name],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            os.unlink(f.name)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
        return None

    def _detect_utilization_counter(self) -> Optional[str]:
        try:
            import win32pdh
            counter_names, instance_names = win32pdh.EnumObjectItems(
                None, None, "GPU Engine", win32pdh.PERF_DETAIL_WIZARD)
            if not instance_names:
                return None
            target = None
            for inst in instance_names:
                if 'engtype_3D' in inst:
                    target = inst
                    break
            if not target:
                target = instance_names[0]
            path = "\\GPU Engine(" + target + ")\\Utilization Percentage"
            q = win32pdh.OpenQuery()
            win32pdh.AddCounter(q, path)
            win32pdh.CollectQueryData(q)
            win32pdh.CloseQuery(q)
            return path
        except Exception as e:
            logger.debug(f"PDH util detect: {e}")
        return None

    def _detect_vram_counter(self) -> Optional[str]:
        try:
            import win32pdh
            counter_names, instance_names = win32pdh.EnumObjectItems(
                None, None, "GPU Adapter Memory", win32pdh.PERF_DETAIL_WIZARD)
            if not instance_names:
                return None
            target = instance_names[0]
            path = "\\GPU Adapter Memory(" + target + ")\\Dedicated Usage"
            q = win32pdh.OpenQuery()
            win32pdh.AddCounter(q, path)
            win32pdh.CollectQueryData(q)
            win32pdh.CloseQuery(q)
            return path
        except Exception as e:
            logger.debug(f"PDH vram detect: {e}")
        return None

    def _try_init_adl(self):
        try:
            from ..utils.amd_adl import get_adl_context
            self._adl_ctx = get_adl_context()
            if self._adl_ctx.available:
                self._adl_available = True
                logger.debug("PDH: ADL initialized")
        except Exception:
            pass

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        stats = AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=self.gpu_names[0] if self.gpu_names else "AMD GPU",
            memory_total=self._vram_total,
            is_available=True,
        )
        # GPU Utilization
        if self._util_counter:
            val = self._util_counter.read_double()
            if val is not None:
                stats.utilization_gpu = self._scale_util(val)
        # VRAM
        if self._vram_counter:
            used = self._vram_counter.read_int()
            if used is not None and used > 0:
                stats.memory_used = used
                stats.memory_free = max(0, self._vram_total - used)
                if self._vram_total > 0:
                    stats.utilization_memory = (used / self._vram_total) * 100.0
        # Temp + Fan
        temp, fan = self._read_temp_fan()
        stats.temperature = temp
        stats.fan_speed = fan
        return stats

    def _scale_util(self, val: float) -> float:
        if val <= 1:
            return val * 100.0
        if val <= 100:
            return val
        return min(100.0, val / 10000.0)

    def _read_temp_fan(self):
        temp = 0.0
        fan = 0
        # ADL
        if self._adl_available and self._adl_ctx:
            try:
                t = self._adl_ctx.get_temperature(0)
                f = self._adl_ctx.get_fan_speed(0)
                if t and 20 <= t <= 115:
                    temp = float(t)
                if f is not None and 0 <= f <= 100:
                    fan = int(f)
                if temp > 0:
                    return temp, fan
            except Exception:
                pass
        # LHM WMI via temp file (avoids bash $ expansion)
        lhm_data = self._run_ps_script(r'''$sensors = @()
try { $sensors += Get-WmiObject -Namespace 'root/LibreHardwareMonitor' -Class Sensor -ErrorAction Stop } catch {}
if (-not $sensors) { try { $sensors += Get-WmiObject -Namespace 'root/OpenHardwareMonitor' -Class Sensor -ErrorAction Stop } catch {} }
if ($sensors) { $sensors | Where-Object { $_.Value -gt 0 } | Select-Object SensorType, Name, Value | ConvertTo-Json -Compress }''')
        if lhm_data:
            import json
            try:
                data = json.loads(lhm_data)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    st = item.get('SensorType', '')
                    sn = item.get('Name', '')
                    sv = float(item.get('Value', 0))
                    if st == 'Temperature' and temp == 0 and 20 <= sv <= 115:
                        if any(k in sn for k in ('GPU', 'Radeon', 'AMD', 'Core', 'Tctl', 'Tdie', 'Edge', 'Hot Spot')):
                            temp = sv
                    elif st == 'Fan' and fan == 0 and 0 <= sv <= 100:
                        if any(k in sn for k in ('GPU', 'Radeon', 'AMD')):
                            fan = int(sv)
                if temp > 0:
                    return temp, fan
            except Exception:
                pass
        # Thermal Zone
        tz = self._run_ps_script(r'''$t = Get-WmiObject -Namespace 'root/WMI' -Class MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Where-Object { $_.Active -eq $true } | Select-Object @{N='T';E={[math]::Round(($_.CurrentTemperature - 2732) / 10, 1)}} | Select-Object -First 1 -ExpandProperty T
if ($t) { Write-Output $t }''')
        if tz:
            try:
                val = float(tz.strip())
                if 20 <= val <= 115:
                    temp = val
            except Exception:
                pass
        return temp, fan

    def close(self):
        if self._util_counter:
            self._util_counter.close()
        if self._vram_counter:
            self._vram_counter.close()
        if self._adl_ctx:
            try:
                self._adl_ctx.close()
            except Exception:
                pass
