"""
ADL (AMD Display Library) Backend
==================================
Direct ctypes binding to atiadlxx.dll on Windows.
"""

import ctypes
import logging
import platform
from ctypes import byref, c_int, c_void_p, c_char, POINTER, Structure

from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)


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


class ADLBackend(MonitorBackend):
    name = "adl"

    def __init__(self):
        super().__init__()
        self._dll = None
        self._context = c_int(0)

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            self._dll = ctypes.windll.LoadLibrary("atiadlxx.dll")
        except:
            try:
                self._dll = ctypes.windll.LoadLibrary("atiadlxy.dll")
            except:
                logger.debug("ADL Backend: atiadlxx.dll not found")
                return False

        # Try to initialize ADL
        try:
            create = self._dll.ADL_Main_Control_Create
            create.restype = c_int
            result = create(0)  # ADL_Main_Control_Create with default
            if result != 0:
                logger.debug(f"ADL Backend: init failed: {result}")
                return False
            self.available = True
            self.gpu_count = 1
            self.gpu_names = ["AMD GPU (ADL)"]
            logger.info("ADL Backend: initialized")
            return True
        except Exception as e:
            logger.debug(f"ADL Backend: init error: {e}")
            return False

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        stats = AMDGPUStats(gpu_id=gpu_id, gpu_name=self.gpu_names[0], is_available=True)

        try:
            # Temperature
            temp = ADLTemperature()
            temp.iSize = ctypes.sizeof(ADLTemperature)
            get_temp = self._dll.ADL_Overdrive5_Temperature_Get
            get_temp.restype = c_int
            if get_temp(gpu_id, 0, byref(temp)) == 0:
                stats.temperature = temp.iTemperature / 1000.0

            # Activity
            activity = ADLPMActivity()
            activity.iSize = ctypes.sizeof(ADLPMActivity)
            get_act = self._dll.ADL_Overdrive5_CurrentActivity_Get
            get_act.restype = c_int
            if get_act(gpu_id, byref(activity)) == 0:
                stats.utilization_gpu = float(activity.iActivityPercent)
                stats.core_clock = activity.iEngineClock
                stats.memory_clock = activity.iMemoryClock

            # Fan speed
            fan = ADLFanSpeedValue()
            fan.iSize = ctypes.sizeof(ADLFanSpeedValue)
            fan.iSpeedType = 0
            get_fan = self._dll.ADL_Overdrive5_FanSpeed_Get
            get_fan.restype = c_int
            if get_fan(gpu_id, 0, byref(fan)) == 0:
                stats.fan_speed = fan.iFanSpeed

        except Exception as e:
            stats.is_available = False
            stats.error_message = str(e)

        return stats

    def close(self):
        try:
            destroy = self._dll.ADL_Main_Control_Destroy
            destroy.restype = c_int
            destroy()
        except:
            pass