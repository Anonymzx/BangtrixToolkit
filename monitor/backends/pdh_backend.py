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

BUG FIXES v4.1 (APU/iGPU Stability):
  - Cached temperature/fan readings (refresh every 10s, NOT per 500ms poll)
  - Added top-level try/except in get_stats() to catch ALL exceptions
  - _run_ps_script now uses try/finally to prevent temp file leaks
  - Added timeout guard for all subprocess calls
"""

import logging
import platform
import time
from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Suppress INFO/DEBUG spam from PDH backend

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

    # Cache temperature/fan — they don't change every 500ms
    # REFRESH every 10 seconds to avoid blocking PowerShell spam
    _TEMP_CACHE_SECONDS = 10.0

    def __init__(self):
        super().__init__()
        self._gpu_name: str = ""
        self._vram_total: int = 0          # Dedicated VRAM in bytes
        self._vram_total_mb: float = 0
        self._shared_vram_total: int = 0   # Shared system memory portion for APU in bytes
        self._is_apu: bool = False
        self._util_counter: Optional[PDHCounter] = None
        self._vram_counter: Optional[PDHCounter] = None      # Dedicated Usage
        self._vram_shared_counter: Optional[PDHCounter] = None  # Shared Usage (APU only)
        self._adl_available: bool = False
        self._adl_ctx = None

        # Temperature/Fan cache — updated every _TEMP_CACHE_SECONDS
        self._cached_temp: float = 0.0
        self._cached_fan: int = 0
        self._last_temp_check: float = 0.0

        # psutil virtual_memory() cache for the APU VRAM proxy. Reusing the
        # temp/fan window keeps psutil off the per-poll hot path (~2 calls/s
        # per APU box) while staying fresh enough for memory pressure to
        # visibly shift the overlay.
        self._cached_psutil_mb: int = 0
        self._cached_psutil_pct: float = 0.0

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            return False

        try:
            self._detect_gpu_info()

            # APU detection: if dedicated VRAM is under 2GB, it's likely an APU
            # AMD Radeon(TM) Graphics (APU) has ~512MB UMA buffer
            self._is_apu = (self._vram_total < 2 * 1024 * 1024 * 1024) and (
                'radeon' in self._gpu_name.lower() or 'amd' in self._gpu_name.lower()
            )

            util_path = self._detect_utilization_counter()
            if util_path:
                self._util_counter = PDHCounter(util_path)
                self._util_counter.open()
            vram_path = self._detect_vram_counter()
            if vram_path:
                self._vram_counter = PDHCounter(vram_path)
                self._vram_counter.open()

            # For APU: attempt Shared Usage counter — SAFE fallback if unavailable
            if self._is_apu:
                try:
                    shared_path = self._detect_vram_shared_counter()
                    if shared_path:
                        self._vram_shared_counter = PDHCounter(shared_path)
                        self._vram_shared_counter.open()
                        self._shared_vram_total = self._get_shared_vram_total()
                        logger.info(f"PDH: APU shared VRAM = {self._shared_vram_total/(1024*1024):.0f}MB")
                except Exception as shared_err:
                    logger.debug(f"PDH: shared VRAM detection skipped ({shared_err}) — using dedicated only")
                    self._shared_vram_total = 0

            self._try_init_adl()

            self.gpu_names = [self._gpu_name] if self._gpu_name else ["AMD GPU"]
            self.gpu_count = 1
            self.available = True

            # Pre-fetch temperature/fan once at init (non-blocking initial value)
            self._refresh_temp_fan_cache()

            # Log effective total VRAM (dedicated + shared for APU)
            effective_vram = self._vram_total + self._shared_vram_total
            logger.info(
                f"PDH: {self.gpu_names[0]} | "
                f"VRAM={self._vram_total_mb:.0f}MB"
                f"{'+' + str(int(self._shared_vram_total/(1024*1024))) + 'MB shared' if self._shared_vram_total > 0 else ''} | "
                f"APU={self._is_apu} | "
                f"Util={'OK' if self._util_counter else 'N/A'} | "
                f"VRAM={'OK' if self._vram_counter else 'N/A'} | "
                f"ADL={'OK' if self._adl_available else 'N/A'}"
            )
            return True
        except Exception as e:
            logger.error(f"PDH Backend: initialize failed: {e}")
            return False

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
        """Fallback GPU detection via WMI (PowerShell tempfile to avoid bash $ expansion).
        NOTE: Only called ONCE at init. Never at runtime."""
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
        """Run PowerShell script via temp file to avoid bash variable expansion.
        FIXED: try/finally ensures temp file cleanup even on timeout."""
        import subprocess, tempfile, os
        f = None
        try:
            f = tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8')
            f.write(script_content)
            f.close()
            fname = f.name
            r = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-NoProfile', '-File', fname],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"PDH: PowerShell script timed out (10s)")
        except Exception:
            pass
        finally:
            # ALWAYS clean up temp file
            if f is not None:
                try:
                    os.unlink(f.name)
                except Exception:
                    pass
        return None

    def _detect_utilization_counter(self) -> Optional[str]:
        """Find a working PDH GPU Engine Utilization Percentage counter.
        For APU systems, instance names contain dynamic PIDs/LUIDs, so exact
        instance matching is unreliable. Instead we use a counter that 
        captures ALL engines via wildcard enumeration at runtime in get_stats().
        
        This function finds ANY valid engtype_3D counter as a fallback.
        The main reading logic in get_stats() uses PS wildcard summation."""
        try:
            import win32pdh
            counter_names, instance_names = win32pdh.EnumObjectItems(
                None, None, "GPU Engine", win32pdh.PERF_DETAIL_WIZARD)
            if not instance_names:
                logger.debug("PDH util detect: no GPU Engine instances found")
                return None

            logger.debug(f"PDH: available GPU Engine instances ({len(instance_names)}): {instance_names[:5]}...")

            # Try engtype_3D instances first (broad match)
            for inst in instance_names:
                if 'engtype_3D' in inst:
                    try:
                        path = "\\GPU Engine(" + inst + ")\\Utilization Percentage"
                        q = win32pdh.OpenQuery()
                        c = win32pdh.AddCounter(q, path)
                        win32pdh.CollectQueryData(q)
                        _, val = win32pdh.GetFormattedCounterValue(c, FMT_DOUBLE | FMT_NOSCALE)
                        win32pdh.CloseQuery(q)
                        logger.debug(f"PDH: util counter: {inst} = {val}")
                        return path
                    except Exception:
                        continue

            # Last resort: any instance with Utilization Percentage
            for inst in instance_names:
                try:
                    path = "\\GPU Engine(" + inst + ")\\Utilization Percentage"
                    q = win32pdh.OpenQuery()
                    c = win32pdh.AddCounter(q, path)
                    win32pdh.CollectQueryData(q)
                    win32pdh.CloseQuery(q)
                    logger.debug(f"PDH: util counter (fallback): {inst}")
                    return path
                except Exception:
                    continue

            logger.debug("PDH util detect: no working counter found")
        except Exception as e:
            logger.debug(f"PDH util detect: {e}")
        return None

    def _detect_vram_counter(self) -> Optional[str]:
        """Find a working PDH GPU Adapter Memory Dedicated Usage counter.
        For APU systems, returns any valid counter as reference.
        Actual VRAM reading uses wildcard summation in get_stats()."""
        try:
            import win32pdh
            counter_names, instance_names = win32pdh.EnumObjectItems(
                None, None, "GPU Adapter Memory", win32pdh.PERF_DETAIL_WIZARD)
            if not instance_names:
                logger.debug("PDH vram detect: no GPU Adapter Memory instances")
                return None

            logger.debug(f"PDH: available Adapter Memory instances: {instance_names}")

            for target in instance_names:
                try:
                    path = "\\GPU Adapter Memory(" + target + ")\\Dedicated Usage"
                    q = win32pdh.OpenQuery()
                    c = win32pdh.AddCounter(q, path)
                    win32pdh.CollectQueryData(q)
                    _, val = win32pdh.GetFormattedCounterValue(c, FMT_LARGE | FMT_NOSCALE)
                    win32pdh.CloseQuery(q)
                    logger.debug(f"PDH: dedicated vram counter: {target} = {val}")
                    return path
                except Exception:
                    continue

            logger.debug("PDH vram detect: no working counter found")
        except Exception as e:
            logger.debug(f"PDH vram detect: {e}")
        return None

    def _detect_vram_shared_counter(self) -> Optional[str]:
        """Detect PDH Shared Usage counter for APU shared system memory.
        For APU we rely on psutil RAM proxy instead of PDH shared counters."""
        return None

    def _get_shared_vram_total(self) -> int:
        """Get the total shared GPU memory available for APU.
        Tries PDH counter first, falls back to WMI query via PowerShell (init only).
        Returns bytes of shared system memory allocated for GPU.
        All exceptions are caught internally — never crashes the backend."""
        # Method 1: Try PDH counter read (instant)
        if self._vram_shared_counter:
            try:
                val = self._vram_shared_counter.read_int()
                if val is not None and val > 0:
                    logger.info(f"PDH: shared VRAM total from counter: {val/(1024*1024):.0f}MB")
                    return val
            except Exception:
                pass

        # Method 2: Use WMI to get total shared GPU memory via Win32_VideoController
        import tempfile, subprocess, os
        fname = None
        try:
            script = r"""$gpu = Get-WmiObject Win32_VideoController | Select-Object -First 1
if ($gpu) {
    # Total shared system memory allocated for GPU
    $shared = $null
    if ($gpu.SharedSystemMemory -gt 0) { $shared = $gpu.SharedSystemMemory }
    # Fallback: use 50% of system RAM
    if (-not $shared -or $shared -eq 0) {
        try {
            $cs = Get-WmiObject Win32_ComputerSystem | Select-Object -First 1
            $shared = [int]($cs.TotalPhysicalMemory * 0.5)
        } catch { $shared = 4GB }
    }
    $shared
} else { 0 }"""
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as f:
                f.write(script)
                fname = f.name
            r = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-NoProfile', '-File', fname],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if r.returncode == 0 and r.stdout.strip():
                val = int(r.stdout.strip())
                if val > 0:
                    logger.info(f"PDH: shared VRAM total from WMI: {val/(1024*1024):.0f}MB")
                    return val
        except Exception as e:
            logger.debug(f"PDH shared vram WMI: {e}")
        finally:
            if fname is not None:
                try:
                    os.unlink(fname)
                except Exception:
                    pass

        # Method 3: Use 50% of system RAM as fallback for APU
        try:
            import psutil
            shared = int(psutil.virtual_memory().total * 0.5)
            logger.info(f"PDH: shared VRAM total from psutil: {shared/(1024*1024):.0f}MB")
            return shared
        except Exception:
            pass

        # Hard fallback: 4GB for APU
        logger.warning("PDH: shared VRAM fallback 4GB for APU")
        return 4 * 1024 * 1024 * 1024

    def _try_init_adl(self):
        try:
            from ..backends.adl_utils import get_adl_context
            self._adl_ctx = get_adl_context()
            if self._adl_ctx.available:
                self._adl_available = True
                logger.debug("PDH: ADL initialized")
        except Exception:
            pass

    def _apu_wildcard_utilization(self) -> float:
        """APU-specific: sum ALL GPU Engine Utilization Percentage counters.
        Uses wildcard-like query to capture all dynamic PID/LUID instances.
        Capped at 100%. Returns 0.0 on failure."""
        import subprocess
        try:
            # Sum ALL utilization percentage counters across ALL GPU engines
            ps_cmd = (
                "Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction SilentlyContinue "
                "| Select-Object -ExpandProperty CounterSamples "
                "| Measure-Object -Property CookedValue -Sum "
                "| Select-Object -ExpandProperty Sum"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if r.returncode == 0 and r.stdout.strip():
                val = float(r.stdout.strip())
                if val > 0:
                    # Raw PDH values represent total across all GPU engines
                    # Windows reports utilization in percentage units already
                    # but can exceed 100 when summing. Cap it.
                    result = min(100.0, max(0.0, val))
                    logger.debug(f"PDH: APU wildcard util sum = {result:.1f}%")
                    return result
        except subprocess.TimeoutExpired:
            logger.debug("PDH: APU util wildcard timed out")
        except Exception as e:
            logger.debug(f"PDH: APU util wildcard error: {e}")
        return 0.0

    def _apu_psutil_vram_used(self, vram_total: int) -> int:
        """APU-specific: estimate VRAM used via system memory pressure.
        Since APU uses shared system RAM, we use psutil memory percentage
        to estimate how much of the shared VRAM pool is in use.
        Falls back to system memory usage as proxy.

        psutil.virtual_memory() is cached for ``_TEMP_CACHE_SECONDS`` so the
        0.5s poll loop doesn't make a syscall on every tick.
        """
        try:
            import psutil
            # Refresh the psutil sample only when the cache window expires.
            now = time.time()
            if now - self._last_temp_check >= self._TEMP_CACHE_SECONDS:
                svmem = psutil.virtual_memory()
                self._cached_psutil_mb = int(svmem.used / (1024 * 1024))
                self._cached_psutil_pct = float(svmem.percent)
            # Use system memory percentage as proxy for VRAM usage
            # APU can dynamically allocate up to ~50% of system RAM for GPU
            # We estimate: used_vram = min(dedicated_uma, ~100%) + shared_pool * mem_usage_pct
            dedicated_uma = self._vram_total  # e.g. 512MB
            shared_pool = max(0, vram_total - dedicated_uma) if vram_total > dedicated_uma else 0
            # Assume UMA is fully committed (APU always uses it)
            # Shared portion usage = pool_size * system_memory_percentage
            dedicated_used = dedicated_uma  # UMA is always "in use" by the GPU
            shared_used = int(shared_pool * (self._cached_psutil_pct / 100.0))
            total_used = dedicated_used + shared_used
            logger.debug(
                f"PDH: APU psutil VRAM proxy: dedicated={dedicated_used}, "
                f"shared={shared_used} (pool={shared_pool}@{self._cached_psutil_pct:.0f}%) = {total_used}"
            )
            return total_used
        except ImportError:
            logger.debug("PDH: psutil not available for VRAM proxy")
        except Exception as e:
            logger.debug(f"PDH: APU VRAM proxy error: {e}")
        return 0

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        """Get GPU stats. APU-optimized with wildcard summation + psutil proxy.
        
        For APU systems:
          - GPU Load = SUM of ALL GPU Engine Utilization Percentage counters
            (captures dynamic PID/LUID-named instances via PS wildcard)
          - VRAM Total = Dedicated (UMA) + 50% of system RAM (psutil)
          - VRAM Used = UMA buffer (fully committed) + shared pool * sys mem %
        
        For dGPU systems:
          - Uses standard PDH counters (instant, no PS subprocess)
        """
        try:
            # Calculate VRAM total
            if self._is_apu:
                # APU: use psutil RAM proxy for VRAM total
                try:
                    import psutil
                    sys_ram = psutil.virtual_memory().total
                    shared_pool = int(sys_ram * 0.5)  # 50% of system RAM
                    vram_total = self._vram_total + shared_pool
                    self._shared_vram_total = shared_pool
                except Exception:
                    vram_total = self._vram_total
                    shared_pool = 0
            else:
                vram_total = self._vram_total
                shared_pool = self._shared_vram_total

            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=self.gpu_names[0] if self.gpu_names else "AMD GPU",
                memory_total=vram_total,
                memory_shared=shared_pool,
                is_apu=self._is_apu,
                is_available=True,
            )

            # === GPU Utilization ===
            if self._is_apu:
                # APU: Always use wildcard summation (captures ALL engines)
                util_read = self._apu_wildcard_utilization()
            else:
                # dGPU: PDH counter (instant, no subprocess)
                util_read = 0.0
                if self._util_counter:
                    val = self._util_counter.read_double()
                    if val is not None:
                        util_read = self._scale_util(val)
                # Fallback to PS if PDH returns 0
                if util_read == 0.0:
                    logger.debug(
                        "PDH: util counter returned 0 on dGPU (%s); "
                        "falling back to PS wildcard summation",
                        self._gpu_name or "AMD GPU",
                    )
                    util_read = self._apu_wildcard_utilization()
            stats.utilization_gpu = util_read

            # === VRAM ===
            if self._is_apu:
                # APU: psutil RAM proxy for VRAM used
                memory_used = self._apu_psutil_vram_used(vram_total)
                stats.memory_used = memory_used
                stats.memory_shared = memory_used - self._vram_total if memory_used > self._vram_total else 0
                stats.memory_free = max(0, vram_total - memory_used)
                if vram_total > 0:
                    stats.utilization_memory = (memory_used / vram_total) * 100.0
            else:
                # dGPU: PDH counter for VRAM
                dedicated_used = 0
                if self._vram_counter:
                    pdh_val = self._vram_counter.read_int()
                    if pdh_val is not None and pdh_val > 0:
                        dedicated_used = pdh_val
                if dedicated_used > 0:
                    stats.memory_used = dedicated_used
                    stats.memory_free = max(0, vram_total - dedicated_used)
                    if vram_total > 0:
                        stats.utilization_memory = (dedicated_used / vram_total) * 100.0

            # Temperature + Fan — CACHED (refreshed every _TEMP_CACHE_SECONDS)
            temp, fan = self._get_cached_temp_fan()
            stats.temperature = temp
            stats.fan_speed = fan
            return stats

        except Exception as e:
            logger.error(f"PDH get_stats error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                gpu_name=self.gpu_names[0] if self.gpu_names else "AMD GPU",
                is_available=False,
                error_message=str(e)
            )

    def _scale_util(self, val: float) -> float:
        if val <= 1:
            return val * 100.0
        if val <= 100:
            return val
        return min(100.0, val / 10000.0)

    def _get_cached_temp_fan(self):
        """Return cached temperature/fan.
        FIXED: Only refreshes every _TEMP_CACHE_SECONDS to avoid
        spawning PowerShell subprocesses every 500ms on APU/iGPU.
        This was the MAIN cause of overlay stacking on slower systems."""
        now = time.time()
        if now - self._last_temp_check >= self._TEMP_CACHE_SECONDS:
            self._refresh_temp_fan_cache()
            self._last_temp_check = now
        return self._cached_temp, self._cached_fan

    def _refresh_temp_fan_cache(self):
        """Refresh the temperature/fan cache.
        This is called at init and every _TEMP_CACHE_SECONDS only.
        NOT on every poll interval."""
        temp = 0.0
        fan = 0

        # Method 1: ADL (instant, no subprocess)
        if self._adl_available and self._adl_ctx:
            try:
                t = self._adl_ctx.get_temperature(0)
                f = self._adl_ctx.get_fan_speed(0)
                if t and 20 <= t <= 115:
                    temp = float(t)
                if f is not None and 0 <= f <= 100:
                    fan = int(f)
                if temp > 0:
                    self._cached_temp = temp
                    self._cached_fan = fan
                    logger.debug(f"PDH: temp/fan from ADL: {temp}°C, {fan}%")
                    return
            except Exception:
                pass

        # Method 2: LHM WMI via temp file
        # Only runs every _TEMP_CACHE_SECONDS (10s), not every 500ms
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
                    self._cached_temp = temp
                    self._cached_fan = fan
                    logger.debug(f"PDH: temp/fan from LHM: {temp}°C, {fan}%")
                    return
            except Exception:
                pass

        # Method 3: Thermal Zone (only runs every 10s)
        tz = self._run_ps_script(r'''$t = Get-WmiObject -Namespace 'root/WMI' -Class MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Where-Object { $_.Active -eq $true } | Select-Object @{N='T';E={[math]::Round(($_.CurrentTemperature - 2732) / 10, 1)}} | Select-Object -First 1 -ExpandProperty T
if ($t) { Write-Output $t }''')
        if tz:
            try:
                val = float(tz.strip())
                if 20 <= val <= 115:
                    temp = val
                    self._cached_temp = temp
                    logger.debug(f"PDH: temp from thermal zone: {temp}°C")
            except Exception:
                pass

        self._cached_temp = temp
        self._cached_fan = fan

    def close(self):
        if self._util_counter:
            self._util_counter.close()
        if self._vram_counter:
            self._vram_counter.close()
        if self._vram_shared_counter:
            self._vram_shared_counter.close()
        if self._adl_ctx:
            try:
                self._adl_ctx.close()
            except Exception:
                pass