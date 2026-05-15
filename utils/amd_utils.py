"""
AMD Utils - GPU Monitoring Backend
===================================
Multi-platform AMD GPU monitoring.
Supports: Linux (ROCm/pyrsmi), Windows (ADL/ADLX, WMI), Fallback (psutil)
"""

import platform
import logging
import subprocess
import re
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class AMDGPUStats:
    gpu_id: int
    gpu_name: str = ""
    utilization_gpu: float = 0.0
    utilization_memory: float = 0.0
    memory_total: int = 0       # Bytes
    memory_used: int = 0        # Bytes
    memory_free: int = 0        # Bytes
    temperature: float = 0.0    # Celsius
    fan_speed: int = 0          # Percent
    core_clock: int = 0         # MHz
    memory_clock: int = 0       # MHz
    power_draw: float = 0.0     # Watts
    is_available: bool = True
    error_message: Optional[str] = None


class AMDMonitor:
    def __init__(self):
        self.available = False
        self.method = None
        self.gpu_count = 0
        self.gpu_names: List[str] = []
        self._backend = None
        self._initialize()

    def _initialize(self):
        system = platform.system()

        # --- LINUX: ROCm / pyrsmi ---
        if system == "Linux":
            try:
                import pyrsmi
                self._backend = pyrsmi
                pyrsmi.rocm_smi_initialize()
                self.method = "pyrsmi"
                self.available = True
                self.gpu_count = pyrsmi.rocm_smi_get_num_devices()
                self.gpu_names = [f"AMD GPU {i}" for i in range(self.gpu_count)]
                logger.info(f"AMD Monitor: ROCm/pyrsmi — {self.gpu_count} GPU(s)")
                return
            except ImportError:
                logger.debug("Linux: pyrsmi not installed")
            except Exception as e:
                logger.warning(f"Linux pyrsmi: {e}")

        # --- WINDOWS ---
        elif system == "Windows":
            # Try ADLX
            if self._try_adlx():
                return
            # Try pyadl
            if self._try_pyadl():
                return
            # WMI-based detection + monitoring (best fallback on Windows)
            if self._try_wmi():
                return
            # Last resort: psutil
            self._try_psutil()

            if self.available:
                return

        if not self.available:
            logger.error(f"AMD Monitor: No backend available on {system}")

    # ==============================================
    # BACKEND DETECTION
    # ==============================================

    def _try_adlx(self):
        try:
            import ctypes
            paths = [
                "C:/Program Files/AMD/ADLX/lib/ADLX.dll",
                "C:/Program Files/AMD/ADLX/bin/ADLX.dll",
            ]
            for path in paths:
                try:
                    self._adlx_dll = ctypes.CDLL(path)
                    self.method = "adlx"
                    self.available = True
                    self._detect_gpu_names_wmi() or self.gpu_names.__setitem__(slice(None), ["AMD GPU 0"])
                    self.gpu_count = max(len(self.gpu_names), 1)
                    logger.info(f"AMD Monitor: ADLX at {path}")
                    return True
                except:
                    continue
        except:
            pass
        return False

    def _try_pyadl(self):
        try:
            import pyadl
            self._backend = pyadl
            try:
                pyadl.ADL2_Main_Control_Create(0)
            except:
                pass
            adapters = pyadl.ADL2_Adapter_AdapterInfo_Get_All()
            present = [a for a in adapters if getattr(a, 'is_present', True)]
            self.gpu_count = len(present)
            self.gpu_names = [getattr(a, 'strAdapterName', f'AMD GPU {i}') for i, a in enumerate(present)]
            self.method = "pyadl"
            self.available = True
            logger.info(f"AMD Monitor: pyadl — {self.gpu_count} GPU(s): {self.gpu_names}")
            return True
        except ImportError:
            pass
        except AttributeError as e:
            logger.debug(f"pyadl API mismatch: {e}")
        except Exception as e:
            logger.warning(f"pyadl error: {e}")
        return False

    def _try_wmi(self):
        """WMI-based detection + monitoring on Windows"""
        # Import the GPU counter monitor module
        success = self._detect_gpu_names_wmi()
        if not success or self.gpu_count == 0:
            return False

        # Try to use the PowerShell counter backend for real utilization data
        try:
            from .amd_gpu_counter import get_gpu_counter
            counter_mon = get_gpu_counter()
            if counter_mon.available:
                self._counter_mon = counter_mon
                self.method = "powershell-counters"
                self.available = True
                # Use names from counter monitor (more accurate)
                if counter_mon.gpu_names:
                    self.gpu_names = counter_mon.gpu_names
                    self.gpu_count = len(self.gpu_names)
                logger.info(f"AMD Monitor: PowerShell counters — {self.gpu_count} GPU(s): {self.gpu_names}")
                return True
        except Exception as e:
            logger.debug(f"GPU counter import failed: {e}")

        # Fallback: basic WMI with no real-time metrics
        self.method = "wmi-basic"
        self.available = True
        logger.info(f"AMD Monitor: WMI basic — {self.gpu_count} GPU(s): {self.gpu_names}")
        return True

    def _try_psutil(self):
        try:
            import psutil
            self.method = "psutil-fallback"
            self.available = True
            self.gpu_count = 1
            self.gpu_names = ["System RAM (no GPU backend)"]
            logger.info("AMD Monitor: psutil-fallback")
        except ImportError:
            pass

    def _detect_gpu_names_wmi(self) -> bool:
        """Use PowerShell to get AMD GPU names via WMI"""
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject Win32_VideoController | "
                "Where-Object { $_.Name -match 'AMD|Radeon|RDNA' } | "
                "Select-Object -ExpandProperty Name"
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                names = [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]
                if names:
                    self.gpu_names = names
                    self.gpu_count = len(names)
                    return True

            # Fallback: get ALL video controllers
            cmd2 = [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty Name"
            ]
            result2 = subprocess.run(
                cmd2, capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result2.returncode == 0 and result2.stdout.strip():
                names = [n.strip() for n in result2.stdout.strip().split('\n') if n.strip()]
                if names:
                    self.gpu_names = names
                    self.gpu_count = len(names)
                    return True
        except Exception as e:
            logger.debug(f"WMI detection error: {e}")
        return False

    # ==============================================
    # GET STATS
    # ==============================================

    def get_gpu_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        if not self.available:
            return AMDGPUStats(
                gpu_id=gpu_id,
                gpu_name="",
                is_available=False,
                error_message="Backend not available"
            )

        try:
            if self.method == "pyrsmi":
                return self._get_stats_linux(gpu_id)
            elif self.method == "adlx":
                return self._get_stats_adlx(gpu_id)
            elif self.method == "pyadl":
                return self._get_stats_pyadl(gpu_id)
            elif self.method in ("wmi", "wmi-basic"):
                return self._get_stats_wmi(gpu_id)
            elif self.method == "powershell-counters":
                return self._get_stats_powershell(gpu_id)
            elif self.method == "psutil-fallback":
                return self._get_stats_psutil(gpu_id)
        except Exception as e:
            return AMDGPUStats(
                gpu_id=gpu_id,
                gpu_name=self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else "",
                is_available=False,
                error_message=str(e)
            )

        return AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else "",
            is_available=False,
            error_message="No matching backend handler"
        )

    def get_all_gpu_stats(self) -> List[AMDGPUStats]:
        if not self.available or self.gpu_count == 0:
            return []
        return [self.get_gpu_stats(i) for i in range(self.gpu_count)]

    # ==============================================
    # BACKEND: Linux / ROCm
    # ==============================================

    def _get_stats_linux(self, gpu_id: int) -> AMDGPUStats:
        rsmi = self._backend

        util = float(rsmi.rocm_smi_get_gpu_utilization(gpu_id))
        mem_total_kb = float(rsmi.rocm_smi_get_gpu_memory_total(gpu_id))
        mem_used_kb = float(rsmi.rocm_smi_get_gpu_memory_used(gpu_id))
        mem_total = int(mem_total_kb * 1024)
        mem_used = int(mem_used_kb * 1024)
        mem_free = mem_total - mem_used
        mem_util = (mem_used / mem_total * 100) if mem_total > 0 else 0
        temp = float(rsmi.rocm_smi_get_temp(gpu_id, 0)) / 1000.0
        fan = int(rsmi.rocm_smi_get_fan_speed(gpu_id, 0))

        core_clk = 0
        mem_clk = 0
        power = 0.0
        try:
            core_clk = int(rsmi.rocm_smi_get_gpu_clk_freq(gpu_id, 0))
            mem_clk = int(rsmi.rocm_smi_get_gpu_clk_freq(gpu_id, 1))
            power = float(rsmi.rocm_smi_get_power_avg(gpu_id)) / 1000.0
        except:
            pass

        name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}"

        return AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=name,
            utilization_gpu=util,
            utilization_memory=mem_util,
            memory_total=mem_total,
            memory_used=mem_used,
            memory_free=mem_free,
            temperature=temp,
            fan_speed=fan,
            core_clock=core_clk,
            memory_clock=mem_clk,
            power_draw=power,
            is_available=True
        )

    # ==============================================
    # BACKEND: Windows / WMI
    # ==============================================

    def _get_stats_wmi(self, gpu_id: int) -> AMDGPUStats:
        """Get GPU stats via PowerShell WMI queries"""
        name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}"

        # Try to get GPU utilization via performance counters
        gpu_util = 0.0
        temp = 0.0
        fan = 0
        mem_used = 0
        mem_total = 0
        mem_free = 0
        mem_util = 0.0

        try:
            # GPU Utilization via PowerShell Performance Counters
            ps_cmd = (
                "Get-Counter '\\GPU Engine(*engtype_3D)\\*' -SampleInterval 0 -MaxSamples 1 "
                "2>$null | Select-Object -ExpandProperty CounterSamples | "
                "Measure-Object -Property CookedValue -Average | "
                "Select-Object -ExpandProperty Average"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                val = float(result.stdout.strip())
                if val > 0:
                    gpu_util = val

            # GPU Temperature via WMI (AMD-specific)
            temp_cmd = (
                "Get-WmiObject -Namespace 'root/OpenHardwareMonitor' -Class Sensor "
                "2>$null | Where-Object { $_.SensorType -eq 'Temperature' -and "
                "$_.Name -match 'GPU' -and $_.Value -gt 0 } | "
                "Select-Object -First 1 -ExpandProperty Value"
            )
            result_temp = subprocess.run(
                ["powershell", "-NoProfile", "-Command", temp_cmd],
                capture_output=True, text=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result_temp.returncode == 0 and result_temp.stdout.strip():
                temp = float(result_temp.stdout.strip())

            # Fallback temperature: read from GPU registry via AMDPowerProfiling
            if temp == 0:
                reg_cmd = (
                    "Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
                    "{4d36e968-e325-11ce-bfc1-08002be10318}\\*' -Name 'AdpaterDesc' -ErrorAction SilentlyContinue "
                    "2>$null | Select-Object -ExpandProperty AdpaterDesc -First 1"
                )

            # Memory (VRAM) via WMI
            vram_cmd = (
                "Get-WmiObject Win32_VideoController | "
                "Select-Object -First 1 -Property AdapterRAM, CurrentHorizontalResolution"
            )
            result_vram = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-WmiObject Win32_VideoController | Select-Object -First 1).AdapterRAM"],
                capture_output=True, text=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result_vram.returncode == 0 and result_vram.stdout.strip():
                mem_total = int(result_vram.stdout.strip())
                # We can't get precise VRAM usage without ADLX, but estimate via process
                if mem_total > 0:
                    mem_util = psutil_vram_estimate()
                    mem_used = int(mem_total * mem_util / 100)
                    mem_free = mem_total - mem_used

        except Exception as e:
            logger.debug(f"WMI stats error: {e}")

        # Fallback to system RAM estimation for VRAM
        if mem_total == 0:
            try:
                import psutil
                svmem = psutil.virtual_memory()
                mem_total = svmem.total
                mem_used = svmem.used
                mem_free = svmem.available
                mem_util = (mem_used / mem_total * 100) if mem_total > 0 else 0
            except:
                pass

        return AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=name,
            utilization_gpu=gpu_util,
            utilization_memory=mem_util,
            memory_total=mem_total,
            memory_used=mem_used,
            memory_free=mem_free,
            temperature=temp,
            fan_speed=fan,
            core_clock=0,
            memory_clock=0,
            power_draw=0,
            is_available=True
        )

    # ==============================================
    # BACKEND: Windows / pyadl
    # ==============================================

    def _get_stats_pyadl(self, gpu_id: int) -> AMDGPUStats:
        adl = self._backend
        name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}"

        try:
            adapters = adl.ADL2_Adapter_AdapterInfo_Get_All()
            active = [a for a in adapters if getattr(a, 'is_present', True)]
            if gpu_id >= len(active):
                return AMDGPUStats(gpu_id=gpu_id, gpu_name=name, is_available=False, error_message="GPU out of range")

            idx = active[gpu_id].adapter_index

            gpu_util = 0.0
            try:
                usage = adl.ADL2_Overdrive6_CurrentUsage_Get(idx, 0)
                gpu_util = float(usage.iEngineClock) / 100.0
            except:
                pass

            temp = 0.0
            try:
                td = adl.ADL2_Overdrive6_Temperature_Get(idx, 0)
                temp = float(td.iTemperature) / 1000.0
            except:
                pass

            fan = 0
            try:
                fd = adl.ADL2_Overdrive6_FanSpeed_Get(idx, 0)
                fan = int(fd.iFanSpeedPercent)
            except:
                pass

            return AMDGPUStats(
                gpu_id=gpu_id,
                gpu_name=name,
                utilization_gpu=gpu_util,
                temperature=temp,
                fan_speed=fan,
                is_available=True
            )
        except Exception as e:
            return AMDGPUStats(gpu_id=gpu_id, gpu_name=name, is_available=False, error_message=str(e))

    # ==============================================
    # BACKEND: Windows / ADLX (placeholder)
    # ==============================================

    def _get_stats_adlx(self, gpu_id: int) -> AMDGPUStats:
        name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}"
        return AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=name,
            is_available=False,
            error_message="ADLX full binding not yet implemented"
        )

    # ==============================================
    # BACKEND: Windows / PowerShell Counters
    # ==============================================

    def _get_stats_powershell(self, gpu_id: int) -> AMDGPUStats:
        """Get GPU stats via PowerShell performance counters"""
        try:
            from .amd_gpu_counter import get_gpu_counter
        except ImportError:
            return self._get_stats_psutil(gpu_id)

        try:
            counter = get_gpu_counter()
            metrics = counter.get_all_metrics(gpu_id)

            name = metrics['gpu_name'] or (self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}")

            # VRAM
            vram = metrics['vram']
            mem_total = int(vram['total_mb'] * 1024 * 1024) if vram['total_mb'] > 0 else 0
            mem_used = int(vram['used_mb'] * 1024 * 1024) if vram['used_mb'] > 0 else 0
            mem_free = int(vram['free_mb'] * 1024 * 1024) if vram['free_mb'] > 0 else mem_total

            # If no VRAM used data, estimate from psutil process memory
            if mem_used == 0 and mem_total > 0:
                mem_util = psutil_vram_estimate()
                mem_used = int(mem_total * mem_util / 100)
                mem_free = mem_total - mem_used
            elif mem_total > 0:
                mem_util = (mem_used / mem_total * 100) if mem_total > 0 else 0
            else:
                # No VRAM data at all — use system RAM as fallback
                try:
                    import psutil
                    svmem = psutil.virtual_memory()
                    mem_total = svmem.total
                    mem_used = svmem.used
                    mem_free = svmem.available
                    mem_util = (mem_used / mem_total * 100) if mem_total > 0 else 0
                    if not name:
                        name = "System RAM (GPU VRAM unavailable)"
                except:
                    mem_util = 0

            return AMDGPUStats(
                gpu_id=gpu_id,
                gpu_name=name,
                utilization_gpu=metrics['utilization'],
                utilization_memory=mem_util,
                memory_total=mem_total,
                memory_used=mem_used,
                memory_free=mem_free,
                temperature=metrics['temperature'],
                fan_speed=metrics['fan_speed'],
                core_clock=0,
                memory_clock=0,
                power_draw=0,
                is_available=True
            )
        except Exception as e:
            logger.warning(f"PowerShell counter error: {e}")
            return self._get_stats_psutil(gpu_id)

    # ==============================================
    # BACKEND: psutil fallback
    # ==============================================

    def _get_stats_psutil(self, gpu_id: int) -> AMDGPUStats:
        import psutil
        svmem = psutil.virtual_memory()
        name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else "System RAM"

        return AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=name,
            utilization_gpu=0.0,
            utilization_memory=(svmem.used / svmem.total * 100) if svmem.total > 0 else 0,
            memory_total=svmem.total,
            memory_used=svmem.used,
            memory_free=svmem.available,
            temperature=0.0,
            fan_speed=0,
            is_available=True
        )


# ==============================================
# HELPERS
# ==============================================

def psutil_vram_estimate() -> float:
    """Rough VRAM usage estimate from process memory"""
    try:
        import psutil
        total = 0
        for proc in psutil.process_iter(['memory_info', 'name']):
            try:
                info = proc.info
                if info.get('memory_info'):
                    total += info['memory_info'].rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        svmem = psutil.virtual_memory()
        return (total / svmem.total * 100) if svmem.total > 0 else 0
    except:
        return 0


# ==============================================
# Singleton
# ==============================================

_amd_monitor = None


def get_amd_monitor():
    global _amd_monitor
    if _amd_monitor is None:
        _amd_monitor = AMDMonitor()
    return _amd_monitor