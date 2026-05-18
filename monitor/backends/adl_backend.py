"""
ADL (AMD Display Library) Backend
==================================
Direct ctypes binding to atiadlxx.dll on Windows.
Provides temperature, fan speed, clock speeds for AMD GPUs.
"""

import ctypes
import logging
import platform
from ctypes import byref, c_int, c_void_p, POINTER, Structure, c_char, c_uint

from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)


# ADL structs
class ADLTemperature(Structure):
    _fields_ = [("iSize", c_int), ("iTemperature", c_int)]


class ADLFanSpeedValue(Structure):
    _fields_ = [("iSize", c_int), ("iSpeedType", c_int), ("iFanSpeed", c_int), ("iFlags", c_int)]


class ADLPMActivity(Structure):
    _fields_ = [
        ("iSize", c_int), ("iEngineClock", c_int), ("iMemoryClock", c_int),
        ("iVddc", c_int), ("iActivityPercent", c_int), ("iCurrentPerformanceLevel", c_int),
        ("iCurrentBusSpeed", c_int), ("iCurrentBusLanes", c_int), ("iUnknown", c_int * 4),
    ]


class ADLODParameters(Structure):
    _fields_ = [
        ("iSize", c_int), ("iStateArraySize", c_int), ("iNumberOfPerformanceStates", c_int),
        ("iNumberOfPerformanceLevels", c_int), ("iEngineClock", c_int), ("iMemoryClock", c_int),
        ("iVddc", c_int), ("iActivityPercent", c_int), ("iCurrentPerformanceLevel", c_int),
        ("iCurrentBusSpeed", c_int), ("iCurrentBusLanes", c_int), ("iUnknown", c_int * 4),
    ]


class ADLAdapterInfo(Structure):
    _fields_ = [
        ("iSize", c_int), ("iAdapterIndex", c_int), ("strUDID", c_char * 256),
        ("iBusNumber", c_int), ("iDeviceNumber", c_int), ("iFunctionNumber", c_int),
        ("iVendorID", c_int), ("iAdapterID", c_int), ("strAdapterName", c_char * 256),
        ("strDisplayName", c_char * 256), ("iPresent", c_int), ("iExist", c_int),
        ("iDriverPath", c_char * 256), ("iDriverPathExt", c_char * 256),
        ("iPNPString", c_char * 256), ("iOSDisplayIndex", c_int),
        ("iBusNumberExt", c_int), ("iDeviceNumberExt", c_int), ("iFunctionNumberExt", c_int),
    ]


class ADLBackend(MonitorBackend):
    """AMD Display Library backend — provides temp, fan, clock for AMD GPUs."""
    name = "adl"

    def __init__(self):
        super().__init__()
        self._dll = None
        self._context = None
        self._adapter_index = 0
        self._available = False

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            return False

        # Load ADL DLL
        try:
            self._dll = ctypes.windll.LoadLibrary("atiadlxx.dll")
        except Exception:
            try:
                self._dll = ctypes.windll.LoadLibrary("atiadlxy.dll")
            except Exception:
                logger.debug("ADL: atiadlxx.dll / atiadlxy.dll not found")
                return False

        # Initialize ADL
        try:
            create = self._dll.ADL_Main_Control_Create
            create.restype = c_int
            create.argtypes = [c_int]
            result = create(0)
            if result != 0:
                logger.debug(f"ADL: Main_Control_Create failed: {result}")
                return False

            # Get number of adapters
            num_adapters = c_int(0)
            info = POINTER(ADLAdapterInfo)()
            get_adapters = self._dll.ADL_Adapter_NumberOfAdapters_Get
            get_adapters.restype = c_int
            get_adapters.argtypes = [POINTER(c_int)]

            if get_adapters(byref(num_adapters)) != 0:
                logger.debug("ADL: Adapter_NumberOfAdapters_Get failed")
                self._shutdown()
                return False

            num = num_adapters.value
            if num <= 0:
                logger.debug("ADL: No adapters found")
                self._shutdown()
                return False

            logger.info(f"ADL Backend: initialized ({num} adapter(s))")
            self._available = True
            self.gpu_count = num
            self.gpu_names = [f"AMD GPU {i}" for i in range(num)]
            self.vendor = "amd"
            self.available = True
            return True

        except Exception as e:
            logger.debug(f"ADL Backend: init error: {e}")
            self._shutdown()
            return False

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        stats = AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}",
            is_available=True,
            vendor="amd",
        )

        try:
            # --- Temperature ---
            try:
                temp = ADLTemperature()
                temp.iSize = ctypes.sizeof(ADLTemperature)
                get_temp = self._dll.ADL_Overdrive5_Temperature_Get
                get_temp.restype = c_int
                get_temp.argtypes = [c_int, c_int, POINTER(ADLTemperature)]
                if get_temp(gpu_id, 0, byref(temp)) == 0:
                    raw_temp = temp.iTemperature
                    if raw_temp > 0:
                        stats.temperature = float(raw_temp) / 1000.0
            except Exception as e:
                logger.debug(f"ADL: temp read error: {e}")

            # --- Activity (GPU Utilization + Clocks) ---
            try:
                activity = ADLPMActivity()
                activity.iSize = ctypes.sizeof(ADLPMActivity)
                get_act = self._dll.ADL_Overdrive5_CurrentActivity_Get
                get_act.restype = c_int
                get_act.argtypes = [c_int, POINTER(ADLPMActivity)]
                if get_act(gpu_id, byref(activity)) == 0:
                    stats.utilization_gpu = float(activity.iActivityPercent)
                    stats.core_clock = activity.iEngineClock
                    stats.memory_clock = activity.iMemoryClock
            except Exception as e:
                logger.debug(f"ADL: activity read error: {e}")

            # --- Fan Speed ---
            try:
                fan = ADLFanSpeedValue()
                fan.iSize = ctypes.sizeof(ADLFanSpeedValue)
                fan.iSpeedType = 0  # ADL_DL_FANCTRL_SPEED_TYPE_PERCENT
                get_fan = self._dll.ADL_Overdrive5_FanSpeed_Get
                get_fan.restype = c_int
                get_fan.argtypes = [c_int, c_int, POINTER(ADLFanSpeedValue)]
                if get_fan(gpu_id, 0, byref(fan)) == 0:
                    stats.fan_speed = int(fan.iFanSpeed)
            except Exception as e:
                logger.debug(f"ADL: fan read error: {e}")

        except Exception as e:
            stats.is_available = False
            stats.error_message = str(e)

        return stats

    def _shutdown(self):
        try:
            destroy = self._dll.ADL_Main_Control_Destroy
            if destroy:
                destroy.restype = c_int
                destroy()
        except Exception:
            pass

    def close(self):
        self._shutdown()