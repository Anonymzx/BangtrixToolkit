"""
AMD SMI Backend
================
Self-contained GPU sensor reader for AMD RDNA3 GPUs (RX 7000 series)
on Windows. Uses two methods with zero external dependencies:

  1. amd-smi.exe (AMD System Management Interface) — subprocess call
  2. ADLX (AMD Display Library Next) — direct ctypes to amdadlx64.dll

Only reads temperature and fan speed. VRAM and utilization are handled
by pdh_backend (PDH counters).

ADL is NOT used — it is incompatible with RDNA3 architecture.
"""

import ctypes
import json
import logging
import os
import platform
import subprocess
from ctypes import byref, c_int, c_void_p, c_char_p, POINTER, Structure, c_uint

from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)


# =====================================================================
# AMD SMI — Subprocess Method
# =====================================================================

def _find_amd_smi() -> str | None:
    """Locate amd-smi.exe on the system."""
    candidates = [
        # AMD ROCm path
        r"C:\Program Files\AMD\ROCm\*\bin\amd-smi.exe",
        # AMD uProf path
        r"C:\Program Files\AMD\AMDuProf\bin\amd-smi.exe",
        r"C:\Program Files\AMD\AMDuProf\bin\amd-smi-cli.exe",
        # System path
        r"C:\Windows\System32\amd-smi.exe",
        # Generic PATH lookup
        "amd-smi.exe",
        "amd-smi-cli.exe",
    ]
    for pattern in candidates:
        import glob
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
        # Also try direct existence
        if os.path.isfile(pattern):
            return pattern
    return None


def _read_temp_via_amd_smi() -> tuple[float, int]:
    """Call amd-smi.exe to read temperature and fan speed.
    
    Returns: (temperature_celsius, fan_speed_percent)
    """
    exe = _find_amd_smi()
    if not exe:
        return 0.0, 0

    try:
        # Try JSON output first
        result = subprocess.run(
            [exe, "metric", "--json"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _parse_amd_smi_json(result.stdout.strip())

        # Try static/legacy output
        result = subprocess.run(
            [exe, "static"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return _parse_amd_smi_text(result.stdout)
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        logger.debug("amd-smi: timed out")
    except Exception as e:
        logger.debug(f"amd-smi: error: {e}")

    return 0.0, 0


def _parse_amd_smi_json(text: str) -> tuple[float, int]:
    """Parse amd-smi --json output for temp/fan."""
    try:
        data = json.loads(text)
        temp = 0.0
        fan = 0

        # Handle different JSON structures across versions
        if isinstance(data, dict):
            gpus = data.get("gpu", data.get("device", data.get("card", [])))
            if isinstance(gpus, dict):
                gpus = [gpus]
        elif isinstance(data, list):
            gpus = data
        else:
            gpus = []

        for gpu in gpus:
            # Temperature
            temp_info = gpu.get("temperature", gpu.get("temp", {}))
            if isinstance(temp_info, dict):
                edge = temp_info.get("edge", temp_info.get("junction", 
                           temp_info.get("hotspot", temp_info.get("gfx", 0))))
                if isinstance(edge, dict):
                    edge = edge.get("value", edge.get("val", 0))
                temp = float(edge) if edge else 0.0
            elif isinstance(temp_info, (int, float)):
                temp = float(temp_info)

            # Fan
            fan_info = gpu.get("fan", gpu.get("fanspeed", gpu.get("fan_speed", {})))
            if isinstance(fan_info, dict):
                speed = fan_info.get("speed", fan_info.get("rpm", 
                           fan_info.get("percent", fan_info.get("value", 0))))
                if isinstance(speed, dict):
                    speed = speed.get("value", speed.get("val", 0))
                fan = int(speed)
            elif isinstance(fan_info, (int, float)):
                fan = int(fan_info)

        return temp, fan
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.debug(f"amd-smi JSON parse: {e}")
        return 0.0, 0


def _parse_amd_smi_text(text: str) -> tuple[float, int]:
    """Parse plain text amd-smi output for temp/fan."""
    temp = 0.0
    fan = 0
    for line in text.split('\n'):
        line_lower = line.lower()
        # Temperature lines
        if 'temperature' in line_lower or 'temp' in line_lower:
            import re
            matches = re.findall(r'(\d+\.?\d*)', line)
            if matches:
                val = float(matches[0])
                if 20 <= val <= 115:
                    temp = val
        # Fan lines
        if 'fan' in line_lower:
            import re
            matches = re.findall(r'(\d+)', line)
            if matches:
                val = int(matches[0])
                if 0 <= val <= 100:
                    fan = val
    return temp, fan


# =====================================================================
# ADLX — ctypes Method
# =====================================================================

# ADLX Result codes
ADLX_OK = 0
ADLX_FAIL = 1

class ADLXResult:
    OK = 0
    FAIL = 1

# Attempt to load ADLX DLL
_adlx_dll = None
_adlx_initialized = False

def _init_adlx() -> bool:
    """Initialize ADLX. Returns True if ready."""
    global _adlx_dll, _adlx_initialized
    if _adlx_initialized:
        return _adlx_dll is not None

    _adlx_initialized = True
    paths = [
        r"C:\Windows\System32\amdadlx64.dll",
    ]
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            _adlx_dll = ctypes.windll.LoadLibrary(path)
            logger.debug(f"ADLX: loaded {path}")
            return True
        except Exception as e:
            logger.debug(f"ADLX: load error: {e}")
    return False


def _read_temp_via_adlx() -> tuple[float, int]:
    """Read temperature and fan via ADLX ctypes."""
    if not _init_adlx():
        return 0.0, 0

    try:
        dll = _adlx_dll

        # ADLX struct definitions
        class AdlxUint(Structure):
            _fields_ = [("value", c_uint)]

        # Temperature Type
        class IAdlxTemperature(Structure):
            _fields_ = [
                ("vtbl", c_void_p),  # vtable pointer
            ]

        # Fan Speed Type
        class IAdlxFanSpeed(Structure):
            _fields_ = [
                ("vtbl", c_void_p),
            ]

        # ADLXHelper - Initialize
        try:
            create = dll.ADLXHelper_Initialize
            if isinstance(create, int):
                create = dll.ADLXHelper_Initialize
            create.restype = c_int
            result = create()
            if result != ADLX_OK:
                logger.debug(f"ADLX: Initialize failed: {result}")
                return 0.0, 0
        except AttributeError:
            logger.debug("ADLX: ADLXHelper_Initialize not found")
            return 0.0, 0

        temp = 0.0
        fan = 0

        # Try to get GPUs
        try:
            # ADLX_IGPUList_GetGPUCount / ADLX_IGPUList_GetGPU
            count_func = dll.ADLX_IGPUList_GetGPUCount
            count_func.restype = c_int
            gpu_count = c_uint(0)
            if count_func(byref(gpu_count)) == ADLX_OK and gpu_count.value > 0:
                # Get GPU at index 0
                gpu_ptr = c_void_p()
                get_gpu = dll.ADLX_IGPUList_GetGPU
                get_gpu.restype = c_int
                get_gpu.argtypes = [c_uint, POINTER(c_void_p)]
                if get_gpu(0, byref(gpu_ptr)) == ADLX_OK and gpu_ptr:
                    # Temperature Sensor
                    temp_ptr = c_void_p()
                    get_temp_sensor = dll.ADLX_IGPU_GetTemperatureSensor
                    get_temp_sensor.restype = c_int
                    get_temp_sensor.argtypes = [c_void_p, POINTER(c_void_p)]
                    if get_temp_sensor(gpu_ptr, byref(temp_ptr)) == ADLX_OK and temp_ptr:
                        val = c_uint(0)
                        get_temp_val = dll.ADLX_ITemperature_GetValue
                        get_temp_val.restype = c_int
                        get_temp_val.argtypes = [c_void_p, POINTER(c_uint)]
                        if get_temp_val(temp_ptr, byref(val)) == ADLX_OK:
                            temp = val.value / 1000.0
                        if temp_ptr:
                            dll.ADLX_ITemperature_Release(temp_ptr)

                    # Fan Speed
                    fan_ptr = c_void_p()
                    get_fan_sensor = dll.ADLX_IGPU_GetFanSpeed
                    get_fan_sensor.restype = c_int
                    get_fan_sensor.argtypes = [c_void_p, POINTER(c_void_p)]
                    if get_fan_sensor(gpu_ptr, byref(fan_ptr)) == ADLX_OK and fan_ptr:
                        fan_val = c_uint(0)
                        get_fan_val = dll.ADLX_IFanSpeed_GetValue
                        get_fan_val.restype = c_int
                        get_fan_val.argtypes = [c_void_p, POINTER(c_uint)]
                        if get_fan_val(fan_ptr, byref(fan_val)) == ADLX_OK:
                            fan = fan_val.value
                        if fan_ptr:
                            dll.ADLX_IFanSpeed_Release(fan_ptr)

                    if gpu_ptr:
                        dll.ADLX_IGPU_Release(gpu_ptr)

        except Exception as e:
            logger.debug(f"ADLX: sensor read error: {e}")

        # Terminate
        try:
            term = dll.ADLXHelper_Terminate
            term.restype = c_int
            term()
        except Exception:
            pass

        return temp, fan

    except Exception as e:
        logger.debug(f"ADLX: error: {e}")
        return 0.0, 0


# =====================================================================
# Composite Backend
# =====================================================================

class AMDSensorBackend(MonitorBackend):
    """AMD sensor backend — temperature and fan for RDNA3 GPUs.
    
    Combines:
      - amd-smi.exe subprocess (primary)
      - ADLX ctypes (fallback)
    
    Does NOT provide VRAM or utilization — pdh_backend handles those.
    """
    name = "amd-sensor"

    def __init__(self):
        super().__init__()
        self._cached_temp = 0.0
        self._cached_fan = 0
        self._temp_fallback_mode = "none"

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            return False

        # Determine available method
        smi_path = _find_amd_smi()
        if smi_path:
            self._temp_fallback_mode = "amd-smi"
            logger.info(f"AMDSensor: using amd-smi ({smi_path})")
        elif _init_adlx():
            self._temp_fallback_mode = "adlx"
            logger.info("AMDSensor: using ADLX")
        else:
            logger.warning("AMDSensor: no AMD sensor method available")
            return False

        self.available = True
        self.gpu_count = 1
        self.gpu_names = ["AMD GPU"]
        self.vendor = "amd"
        return True

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        stats = AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name="AMD GPU",
            is_available=True,
            vendor="amd",
        )

        if self._temp_fallback_mode == "amd-smi":
            temp, fan = _read_temp_via_amd_smi()
            stats.temperature = temp
            stats.fan_speed = fan
        elif self._temp_fallback_mode == "adlx":
            temp, fan = _read_temp_via_adlx()
            stats.temperature = temp
            stats.fan_speed = fan

        return stats