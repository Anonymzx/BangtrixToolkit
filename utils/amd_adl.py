"""
AMD ADL (Display Library) Direct Binding
=========================================
Low-level ctypes binding to atiadlxx.dll for GPU monitoring on Windows.
No dependencies required (uses ctypes which is built-in Python).

Provides: GPU Utilization, Temperature, Fan Speed, GPU Name, Core/Memory Clocks
"""

import ctypes
import ctypes.util
import logging
import platform
from ctypes import byref, c_int, c_void_p, c_char_p, c_char, POINTER, Structure

logger = logging.getLogger(__name__)

# =============================================
# DLL LOADING
# =============================================

_adl_dll = None
_adl_initialized = False


def _load_adl():
    global _adl_dll
    if _adl_dll is not None:
        return True

    system = platform.system()
    if system != "Windows":
        return False

    try:
        _adl_dll = ctypes.windll.LoadLibrary("atiadlxx.dll")
        logger.debug("ADL: loaded atiadlxx.dll from System32")
        return True
    except:
        try:
            _adl_dll = ctypes.windll.LoadLibrary("atiadlxy.dll")
            logger.debug("ADL: loaded atiadlxy.dll (fallback)")
            return True
        except:
            logger.debug("ADL: cannot load atiadlxx.dll / atiadlxy.dll")
            return False


# =============================================
# ADL TYPES
# =============================================

class ADLAdapterInfo(Structure):
    _fields_ = [
        ("strAdapterName", c_char * 256),
        ("iAdapterIndex", c_int),
        ("iBusNumber", c_int),
        ("iDeviceNumber", c_int),
        ("iFunctionNumber", c_int),
        ("iVendorID", c_int),
        ("strAdapterName_256", c_char * 256),
        ("isPresent", c_int),
        ("iDisplayType", c_int * 4),
        ("iFormFactor", c_int),
        ("iClusterInfo", c_int),
        ("strBusString", c_char * 64),
        ("strBusNumber", c_char * 64),
        ("iFunction", c_int),
        ("iRevisionID", c_int),
        ("iExtendedRevisionID", c_int),
        ("iMemorySizeMB", c_int),
    ]


class ADLTemperature(Structure):
    _fields_ = [
        ("iSize", c_int),
        ("iTemperature", c_int),
    ]


class ADLFanSpeedValue(Structure):
    _fields_ = [
        ("iSize", c_int),
        ("iSpeedType", c_int),
        ("iFanSpeed", c_int),
        ("iFlags", c_int),
    ]


class ADLPMActivity(Structure):
    _fields_ = [
        ("iSize", c_int),
        ("iEngineClock", c_int),
        ("iMemoryClock", c_int),
        ("iVddc", c_int),
        ("iActivityPercent", c_int),
        ("iCurrentPerformanceLevel", c_int),
        ("iCurrentBusSpeed", c_int),
        ("iCurrentBusLanes", c_int),
        ("iUnknown", c_int * 4),
    ]


class ADLODParameters(Structure):
    _fields_ = [
        ("iSize", c_int),
        ("iEngineClock", c_int),
        ("iMemoryClock", c_int),
        ("iVddc", c_int),
        ("iActivityPercent", c_int),
        ("iCurrentPerformanceLevel", c_int),
        ("iCurrentMinEngineClock", c_int),
        ("iCurrentMinMemoryClock", c_int),
        ("iCurrentMaxEngineClock", c_int),
        ("iCurrentMaxMemoryClock", c_int),
    ]


# =============================================
# ADL CONTEXT
# =============================================

class ADLContext:
    """Manages ADL lifecycle and GPU adapter info"""

    def __init__(self):
        self.available = False
        self.num_adapters = 0
        self.adapters = []
        self.adapter_names = []
        self._context = None

    def initialize(self) -> bool:
        if not _load_adl():
            return False

        try:
            # ADL2_Main_Control_Create(callback, enumConnectedAdapters)
            ADL2_Main_Control_Create = _adl_dll.ADL2_Main_Control_Create
            ADL2_Main_Control_Create.argtypes = [c_void_p, c_int]
            ADL2_Main_Control_Create.restype = c_int

            context = c_int(0)
            result = ADL2_Main_Control_Create(None, byref(context))
            if result != 0:
                logger.warning(f"ADL: Main_Control_Create failed: {result}")
                return False

            self._context = context

            # Get adapter count
            ADL2_Adapter_NumberOfAdapters_Get = _adl_dll.ADL2_Adapter_NumberOfAdapters_Get
            ADL2_Adapter_NumberOfAdapters_Get.argtypes = [c_int, POINTER(c_int)]
            ADL2_Adapter_NumberOfAdapters_Get.restype = c_int

            num = c_int(0)
            result = ADL2_Adapter_NumberOfAdapters_Get(context.value, byref(num))
            if result != 0:
                logger.warning(f"ADL: NumberOfAdapters_Get failed: {result}")
                self._destroy()
                return False

            self.num_adapters = num.value

            # Query adapter info for all adapters
            if self.num_adapters > 0:
                self._query_adapters()

            self.available = True
            logger.info(f"ADL: Initialized — {len(self.adapters)} adapter(s)")
            return True

        except Exception as e:
            logger.warning(f"ADL: Init error: {e}")
            return False

    def _query_adapters(self):
        """Get adapter info for all adapters"""
        try:
            ADL2_Adapter_AdapterInfo_Get = _adl_dll.ADL2_Adapter_AdapterInfo_Get
            ADL2_Adapter_AdapterInfo_Get.argtypes = [c_int, c_void_p, POINTER(c_int)]
            ADL2_Adapter_AdapterInfo_Get.restype = c_int

            # Allocate memory via ADL
            ADL2_Main_Memory_Alloc = _adl_dll.ADL2_Main_Memory_Alloc
            ADL2_Main_Memory_Alloc.argtypes = [c_int, c_int, c_void_p]
            ADL2_Main_Memory_Alloc.restype = c_int

            buf_size = c_int(ctypes.sizeof(ADLAdapterInfo) * self.num_adapters)
            buffer = ctypes.create_string_buffer(buf_size.value)

            # Use our own buffer, ADL will read present adapters
            result = ADL2_Adapter_AdapterInfo_Get(
                self._context.value,
                buffer,
                byref(buf_size)
            )

            if result == 0:
                info_array = (ADLAdapterInfo * self.num_adapters).from_buffer(buffer)
                total = min(self.num_adapters, buf_size.value // ctypes.sizeof(ADLAdapterInfo))
                for i in range(total):
                    info = info_array[i]
                    if info.isPresent or info.iAdapterIndex >= 0:
                        name = info.strAdapterName.decode('utf-8', errors='replace').strip()
                        if not name:
                            name = info.strAdapterName_256.decode('utf-8', errors='replace').strip()
                        self.adapters.append({
                            'index': info.iAdapterIndex,
                            'name': name,
                        })
                        self.adapter_names.append(name)

            # Fallback: if no adapters found, try ADL2_Adapter_AdapterInfo_Get_All
            if len(self.adapters) == 0:
                self._query_adapters_fallback()

        except Exception as e:
            logger.warning(f"ADL: AdapterInfo error: {e}")
            self.adapters = [{'index': 0, 'name': 'AMD GPU 0'}]
            self.adapter_names = ['AMD GPU 0']

    def _query_adapters_fallback(self):
        """Fallback: just create virtual adapters based on count"""
        for i in range(self.num_adapters):
            self.adapters.append({'index': i, 'name': f'AMD GPU {i}'})
            self.adapter_names.append(f'AMD GPU {i}')

    def get_temperature(self, adapter_index: int) -> float:
        """Get GPU temperature in Celsius"""
        try:
            ADL2_Overdrive6_Temperature_Get = _adl_dll.ADL2_Overdrive6_Temperature_Get
            ADL2_Overdrive6_Temperature_Get.argtypes = [c_int, c_int, POINTER(ADLTemperature)]
            ADL2_Overdrive6_Temperature_Get.restype = c_int

            temp = ADLTemperature()
            temp.iSize = ctypes.sizeof(ADLTemperature)
            result = ADL2_Overdrive6_Temperature_Get(self._context.value, adapter_index, byref(temp))
            if result == 0:
                return temp.iTemperature / 1000.0
        except:
            pass
        return 0.0

    def get_fan_speed(self, adapter_index: int) -> int:
        """Get GPU fan speed in percent"""
        try:
            ADL2_Overdrive6_FanSpeed_Get = _adl_dll.ADL2_Overdrive6_FanSpeed_Get
            ADL2_Overdrive6_FanSpeed_Get.argtypes = [c_int, c_int, POINTER(ADLFanSpeedValue)]
            ADL2_Overdrive6_FanSpeed_Get.restype = c_int

            fan = ADLFanSpeedValue()
            fan.iSize = ctypes.sizeof(ADLFanSpeedValue)
            fan.iSpeedType = 0  # ADL_DL_FANCTRL_SPEED_TYPE_PERCENT
            result = ADL2_Overdrive6_FanSpeed_Get(self._context.value, adapter_index, byref(fan))
            if result == 0:
                return fan.iFanSpeed
        except:
            pass
        return 0

    def get_activity(self, adapter_index: int):
        """Get GPU activity: utilization, engine clock, memory clock"""
        try:
            ADL2_Overdrive6_CurrentActivity_Get = _adl_dll.ADL2_Overdrive6_CurrentActivity_Get
            ADL2_Overdrive6_CurrentActivity_Get.argtypes = [c_int, c_int, POINTER(ADLPMActivity)]
            ADL2_Overdrive6_CurrentActivity_Get.restype = c_int

            activity = ADLPMActivity()
            activity.iSize = ctypes.sizeof(ADLPMActivity)
            result = ADL2_Overdrive6_CurrentActivity_Get(self._context.value, adapter_index, byref(activity))
            if result == 0:
                return {
                    'utilization': activity.iActivityPercent,
                    'engine_clock': activity.iEngineClock,
                    'memory_clock': activity.iMemoryClock,
                }
        except:
            pass
        return {'utilization': 0, 'engine_clock': 0, 'memory_clock': 0}

    def get_memory_info(self, adapter_index: int):
        """Get VRAM size in MB"""
        # Memory info from adapter info
        for adapter in self.adapters:
            if adapter['index'] == adapter_index:
                # We stored the adapter index, but not memory size directly
                pass
        return 0

    def _destroy(self):
        """Clean up ADL context"""
        try:
            if self._context is not None:
                ADL2_Main_Control_Destroy = _adl_dll.ADL2_Main_Control_Destroy
                ADL2_Main_Control_Destroy.argtypes = [c_int]
                ADL2_Main_Control_Destroy.restype = c_int
                ADL2_Main_Control_Destroy(self._context.value)
                self._context = None
        except:
            pass

    def close(self):
        self._destroy()


# =============================================
# GLOBAL ADL INSTANCE
# =============================================

_adl_context = None


def get_adl_context() -> ADLContext:
    global _adl_context
    if _adl_context is None:
        ctx = ADLContext()
        if ctx.initialize():
            _adl_context = ctx
        else:
            _adl_context = ctx  # Return anyway, .available will be False
    return _adl_context


# =============================================
# TEST
# =============================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    ctx = get_adl_context()
    if ctx.available:
        print(f"ADL: {len(ctx.adapters)} adapter(s)")
        for i, adapter in enumerate(ctx.adapters):
            print(f"  GPU {i}: {adapter['name']} (index={adapter['index']})")

            temp = ctx.get_temperature(adapter['index'])
            fan = ctx.get_fan_speed(adapter['index'])
            activity = ctx.get_activity(adapter['index'])

            print(f"    Temp: {temp:.1f}°C")
            print(f"    Fan: {fan}%")
            print(f"    Utilization: {activity['utilization']}%")
            print(f"    Engine Clock: {activity['engine_clock']} MHz")
            print(f"    Memory Clock: {activity['memory_clock']} MHz")
    else:
        print("ADL: Not available")