import platform
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AMDGPUStats:
    gpu_id: int
    utilization_gpu: float
    utilization_memory: float
    memory_total: int       # Bytes
    memory_used: int        # Bytes
    memory_free: int        # Bytes
    temperature: float
    fan_speed: int
    is_available: bool
    error_message: Optional[str] = None


class AMDMonitor:
    def __init__(self):
        self.available = False
        self.method = None
        self.gpu_count = 0
        self._backend = None
        self._initialize()

    def _initialize(self):
        system = platform.system()
        
        # --- LINUX IMPLEMENTATION (ROCm) ---
        if system == "Linux":
            try:
                import pyrsmi
                self._backend = pyrsmi
                pyrsmi.rocm_smi_initialize()
                self.method = "pyrsmi"
                self.available = True
                self.gpu_count = pyrsmi.rocm_smi_get_num_devices()
                logger.info(f"AMD Monitor: Linux detected, using pyrsmi. Found {self.gpu_count} GPUs.")
                return
            except ImportError:
                logger.warning("Linux detected but 'pyrsmi' not installed.")
            except Exception as e:
                logger.warning(f"Linux pyrsmi init failed: {e}")

        # --- WINDOWS IMPLEMENTATION (ADL) ---
        elif system == "Windows":
            try:
                import pyadl
                self._backend = pyadl
                
                # Try init without custom allocator (safer)
                try:
                    res = pyadl.ADL2_Main_Control_Create(0)  # Use default allocator
                except:
                    res = 0  # Assume success if function doesn't exist
                
                if res == 0:
                    adapters = pyadl.ADL2_Adapter_AdapterInfo_Get_All()
                    self.gpu_count = len([a for a in adapters if getattr(a, 'is_present', True)])
                    self.method = "pyadl"
                    self.available = True
                    logger.info(f"AMD Monitor: Windows + pyadl. Found {self.gpu_count} GPUs.")
                    return
            except ImportError:
                logger.warning("Windows: pyadl not installed")
            except Exception as e:
                logger.warning(f"Windows pyadl error: {e}")
            
            # Fallback: Try psutil for basic system info
            try:
                import psutil
                self.method = "psutil-fallback"
                self.available = True  # Partial availability
                self.gpu_count = 1  # Assume 1 GPU for fallback
                logger.info("AMD Monitor: Using psutil fallback (limited AMD info)")
                return
            except ImportError:
                pass

        logger.error("No AMD monitoring backend available. Check requirements.")

    def get_gpu_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        if not self.available:
            return AMDGPUStats(gpu_id, 0, 0, 0, 0, 0, 0, 0, False, "Backend not available")

        try:
            if self.method == "pyrsmi":
                return self._get_stats_linux(gpu_id)
            elif self.method == "pyadl":
                return self._get_stats_windows(gpu_id)
            elif self.method == "psutil-fallback":
                return self._get_stats_windows_fallback(gpu_id)
        except Exception as e:
            return AMDGPUStats(gpu_id, 0, 0, 0, 0, 0, 0, 0, False, str(e))

    def _get_stats_linux(self, gpu_id: int) -> AMDGPUStats:
        rsmi = self._backend
        # Utilization
        util = rsmi.rocm_smi_get_gpu_utilization(gpu_id)
        
        # Memory (ROCm returns KB, convert to Bytes)
        mem_total_kb = rsmi.rocm_smi_get_gpu_memory_total(gpu_id)
        mem_used_kb = rsmi.rocm_smi_get_gpu_memory_used(gpu_id)
        
        mem_total = mem_total_kb * 1024
        mem_used = mem_used_kb * 1024
        mem_free = mem_total - mem_used
        mem_util = (mem_used / mem_total) * 100 if mem_total > 0 else 0
        
        # Temp (ROCm returns mC, convert to C)
        temp = rsmi.rocm_smi_get_temp(gpu_id, 0) / 1000.0
        
        # Fan
        fan = rsmi.rocm_smi_get_fan_speed(gpu_id, 0)

        return AMDGPUStats(
            gpu_id=gpu_id,
            utilization_gpu=util,
            utilization_memory=mem_util,
            memory_total=mem_total,
            memory_used=mem_used,
            memory_free=mem_free,
            temperature=temp,
            fan_speed=fan,
            is_available=True
        )

    def _get_stats_windows(self, gpu_id: int) -> AMDGPUStats:
        adl = self._backend
        adapters = adl.ADL2_Adapter_AdapterInfo_Get_All()
        active_adapters = [a for a in adapters if getattr(a, 'is_present', True)]
        
        if gpu_id >= len(active_adapters):
            return AMDGPUStats(gpu_id, 0, 0, 0, 0, 0, 0, 0, False, "GPU Index out of range")
            
        adapter = active_adapters[gpu_id]
        adapter_index = adapter.adapter_index

        # Utilization (Overdrive6 is for GCN and newer)
        gpu_util = 0
        try:
            usage = adl.ADL2_Overdrive6_CurrentUsage_Get(adapter_index, 0)
            gpu_util = usage.iEngineClock
        except:
            pass

        # Memory (VRAM) - ADL doesn't expose this easily
        mem_used = 0
        mem_total = 0
        mem_util = 0
        
        # Temperature
        temp = 0
        try:
            temp_data = adl.ADL2_Overdrive6_Temperature_Get(adapter_index, 0)
            temp = temp_data.iTemperature / 1000.0  # ADL returns in milli-Celsius
        except:
            pass
            
        # Fan Speed
        fan = 0
        try:
            fan_data = adl.ADL2_Overdrive6_FanSpeed_Get(adapter_index, 0)
            fan = fan_data.iFanSpeedPercent
        except:
            pass
            
        return AMDGPUStats(
            gpu_id=gpu_id,
            utilization_gpu=gpu_util, 
            utilization_memory=mem_util,
            memory_total=mem_total,
            memory_used=mem_used,
            memory_free=0,
            temperature=temp,
            fan_speed=fan,
            is_available=True
        )

    def _get_stats_windows_fallback(self, gpu_id: int) -> AMDGPUStats:
        """Fallback using psutil when ADL fails"""
        import psutil
        
        # Basic system memory (not GPU-specific, but better than nothing)
        svmem = psutil.virtual_memory()
        
        return AMDGPUStats(
            gpu_id=gpu_id,
            utilization_gpu=0,
            utilization_memory=(svmem.used / svmem.total * 100),
            memory_total=svmem.total,
            memory_used=svmem.used,
            memory_free=svmem.available,
            temperature=0,
            fan_speed=0,
            is_available=True
        )


# Singleton
_amd_monitor = None

def get_amd_monitor():
    global _amd_monitor
    if _amd_monitor is None:
        _amd_monitor = AMDMonitor()
    return _amd_monitor