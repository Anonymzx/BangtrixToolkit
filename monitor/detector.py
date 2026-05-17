"""
Hardware Detector - OS and GPU vendor auto-detection
====================================================
Detects the operating system and available GPU vendor(s) using
zero or minimal external dependencies. This is the first step
in the Universal Monitor initialization chain.

Detection Strategy:
  1. OS detection (Windows vs Linux)
  2. GPU vendor detection (AMD, NVIDIA, Intel, or unknown)
  3. APU/iGPU detection (shared memory GPUs)
  
All methods use standard library only — no pip installs required.
"""

import logging
import platform
import os
import re
import subprocess
import json
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# -------------------- OS Detection --------------------

def detect_os() -> str:
    """Detect the operating system.
    
    Returns:
        "windows", "linux", or "unknown"
    """
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    return "unknown"


# -------------------- GPU Vendor Detection --------------------

def detect_gpu_vendors_windows() -> List[dict]:
    """Detect GPU vendors on Windows using Registry (win32api) or fallback to WMI/PowerShell.
    
    Returns:
        List of dicts: [{'name': str, 'vendor': str, 'vram_bytes': int}, ...]
    """
    gpus = []
    
    # Method 1: Windows Registry (zero dependency, fastest)
    try:
        import winreg
        gpu_key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, gpu_key_path) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        try:
                            desc, _ = winreg.QueryValueEx(subkey, "DriverDesc")
                            if desc and isinstance(desc, str) and len(desc) > 3:
                                vendor = _identify_vendor(desc)
                                vram = _read_vram_registry(subkey)
                                gpus.append({
                                    'name': desc,
                                    'vendor': vendor,
                                    'vram_bytes': vram,
                                })
                        except (FileNotFoundError, OSError):
                            pass
                    i += 1
                except OSError:
                    break
    except ImportError:
        logger.debug("Detector: winreg not available")
    except Exception as e:
        logger.debug(f"Detector: registry scan error: {e}")
    
    if gpus:
        logger.info(f"Detector: Found {len(gpus)} GPU(s) via registry: {[g['vendor'] for g in gpus]}")
        return gpus
    
    # Method 2: PowerShell WMI fallback (one-time)
    try:
        ps_script = (
            "Get-WmiObject Win32_VideoController | "
            "Select-Object Name, AdapterRAM, VideoModeDescription, DriverVersion | "
            "ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
        if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != 'null':
            data = json.loads(result.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            for item in data:
                name = item.get('Name', '') or ''
                vram = int(item.get('AdapterRAM', 0) or 0)
                vendor = _identify_vendor(name)
                gpus.append({
                    'name': name,
                    'vendor': vendor,
                    'vram_bytes': vram,
                })
    except Exception as e:
        logger.debug(f"Detector: WMI fallback error: {e}")
    
    if not gpus:
        logger.warning("Detector: No GPUs found on Windows")
    
    return gpus


def detect_gpu_vendors_linux() -> List[dict]:
    """Detect GPU vendors on Linux by parsing /sys/class/drm/ and /proc/bus/pci/devices.
    
    Uses standard library only — reads sysfs virtual files.
    
    Returns:
        List of dicts: [{'name': str, 'vendor': str, 'vram_bytes': int}, ...]
    """
    gpus = []
    
    # Method 1: /sys/class/drm/ — the standard Linux GPU interface
    drm_path = "/sys/class/drm"
    if os.path.exists(drm_path):
        try:
            for entry in os.listdir(drm_path):
                device_path = os.path.join(drm_path, entry)
            
                # Only look at card devices, not renderD*
                if not entry.startswith("card") or "card" not in entry:
                    continue
                # Skip the -HDMI/-DP sub-devices
                if "-" in entry:
                    continue
            
                # Read device vendor/name via PCI
                vendor_file = os.path.join(device_path, "device", "vendor")
                if not os.path.exists(vendor_file):
                    # Try symlink resolution
                    try:
                        real = os.path.realpath(device_path)
                        # Navigate up to find PCI device
                        pci_path = real
                        for _ in range(5):
                            pci_path = os.path.dirname(pci_path)
                            vendor_f = os.path.join(pci_path, "vendor")
                            if os.path.exists(vendor_f):
                                vendor_file = vendor_f
                                break
                    except Exception:
                        pass
            
                vendor_id = ""
                device_name = ""
                vram_bytes = 0
            
                # Read vendor ID
                if os.path.exists(vendor_file):
                    try:
                        with open(vendor_file, 'r') as f:
                            vendor_id = f.read().strip()
                    except Exception:
                        pass
            
                # Determine vendor from PCI vendor ID
                vendor = _pci_vendor_to_name(vendor_id)
            
                # Read GPU name from device subdirectory
                dev_name_file = os.path.join(device_path, "device", "device")
                if os.path.exists(dev_name_file):
                    try:
                        with open(dev_name_file, 'r') as f:
                            device_id = f.read().strip()
                        device_name = f"GPU ({vendor} 0x{device_id})"
                    except Exception:
                        device_name = f"GPU ({vendor})"
                else:
                    device_name = f"GPU ({vendor})"
            
                # Read VRAM size for AMD via amdgpu sysfs
                if vendor == "amd":
                    vram_bytes = _read_amdgpu_vram_linux(device_path)
            
                # Read VRAM for Intel
                if vendor == "intel":
                    vram_bytes = _read_intel_vram_linux()
            
                # Avoid duplicates (same card may appear multiple times)
                if not any(g['vendor'] == vendor for g in gpus):
                    gpus.append({
                        'name': device_name,
                        'vendor': vendor,
                        'vram_bytes': vram_bytes,
                    })
                    
        except PermissionError:
            logger.debug("Detector: Permission denied reading /sys/class/drm (try sudo or non-root)")
        except Exception as e:
            logger.debug(f"Detector: /sys/class/drm error: {e}")
    
    # Method 2: /proc/bus/pci/devices fallback
    if not gpus:
        gpus = _detect_gpu_via_pci_proc()
    
    # Method 3: nvidia-smi for NVIDIA (even for vendor detection)
    if not gpus or not any(g['vendor'] == 'nvidia' for g in gpus):
        _detect_nvidia_via_smi(gpus)
    
    # Method 4: lspci as last resort
    if not gpus:
        _detect_gpu_via_lspci(gpus)
    
    if not gpus:
        logger.warning("Detector: No GPUs found on Linux")
    
    return gpus


# -------------------- Vendor Identification --------------------

def _identify_vendor(name: str) -> str:
    """Identify GPU vendor from a device name string."""
    name_lower = name.lower()
    if 'nvidia' in name_lower or 'geforce' in name_lower or 'quadro' in name_lower or 'tesla' in name_lower:
        return 'nvidia'
    if 'amd' in name_lower or 'radeon' in name_lower or 'firepro' in name_lower or 'instinct' in name_lower:
        return 'amd'
    if 'intel' in name_lower or 'arc' in name_lower or 'iris' in name_lower or 'uhd graphics' in name_lower or 'hd graphics' in name_lower:
        return 'intel'
    if 'microsoft' in name_lower or 'virtualbox' in name_lower or 'vmware' in name_lower:
        return 'virtual'
    return 'unknown'


def _pci_vendor_to_name(vendor_id: str) -> str:
    """Map PCI vendor ID to vendor name."""
    vid = vendor_id.strip().lower().replace('0x', '')
    mapping = {
        '1002': 'amd',
        '10de': 'nvidia',
        '8086': 'intel',
        '102b': 'matrox',
        '1a03': 'aspeed',
        '1414': 'microsoft',
    }
    return mapping.get(vid, 'unknown')


def _read_vram_registry(subkey) -> int:
    """Read VRAM from a Windows registry subkey."""
    try:
        import winreg
        vram_names = [
            'HardwareInformation.qwMemorySize',
            'HardwareInformation.GpuMemorySize',
            'HardwareInformation.MemorySize',
            'UMA_FB_SIZE',
        ]
        for val_name in vram_names:
            try:
                val, _ = winreg.QueryValueEx(subkey, val_name)
                if val is None or val == 0:
                    continue
                if isinstance(val, bytes) and len(val) >= 8:
                    import struct
                    val = struct.unpack('Q', val[:8])[0]
                elif isinstance(val, bytes) and len(val) >= 4:
                    import struct
                    val = struct.unpack('I', val[:4])[0]
                elif isinstance(val, str):
                    try:
                        val = int(val)
                    except (ValueError, TypeError):
                        continue
                elif not isinstance(val, (int, float)):
                    continue
                
                val = int(val)
                if val <= 0:
                    continue
                
                # APU UMA_FB_SIZE is in MB
                if val_name == 'UMA_FB_SIZE' and val < 1024 * 1024:
                    val = val * 1024 * 1024
                
                # Sanity check: 128MB to 256GB
                if 128 * 1024 * 1024 <= val <= 256 * 1024 * 1024 * 1024:
                    return val
            except (FileNotFoundError, OSError):
                pass
    except ImportError:
        pass
    except Exception:
        pass
    return 0


# -------------------- Linux-specific Helpers --------------------

def _read_amdgpu_vram_linux(device_path: str) -> int:
    """Read VRAM size for AMD GPUs on Linux via amdgpu sysfs."""
    # Try amdgpu specific path
    vram_paths = [
        os.path.join(device_path, "device", "gpu_vram_size"),  # Some kernels
        os.path.join(device_path, "gt"),  # Fallback
    ]
    
    for vp in vram_paths:
        if os.path.exists(vp):
            try:
                with open(vp, 'r') as f:
                    val = f.read().strip()
                return int(val)  # In bytes on newer kernels
            except (ValueError, OSError):
                pass
    
    # Try reading from amdgpu firmware info in debugfs
    try:
        mem_info = "/sys/kernel/debug/dri/0/amdgpu_vram_mm"
        if os.path.exists(mem_info):
            with open(mem_info, 'r') as f:
                content = f.read()
                match = re.search(r'total: (\d+)', content)
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    
    return 0


def _read_intel_vram_linux() -> int:
    """Read VRAM for Intel GPUs on Linux."""
    # Intel integrated GPUs use shared memory — read system RAM
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    parts = line.split()
                    if len(parts) >= 2:
                        kb = int(parts[1])
                        return kb * 1024  # Convert KB to bytes
    except Exception:
        pass
    return 0


def _detect_gpu_via_pci_proc() -> List[dict]:
    """Fallback: read /proc/bus/pci/devices for GPU detection."""
    gpus = []
    try:
        pci_path = "/proc/bus/pci/devices"
        if not os.path.exists(pci_path):
            return gpus
        
        with open(pci_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                # Bus address is in parts[0]
                # Vendor:Device is in parts[1] as hex
                vendor_device = parts[1].split()
                if not vendor_device:
                    continue
                
                pci_id = vendor_device[0].lower()
                # Class 0x03xxxx is display controller
                cls = parts[2].lower() if len(parts) > 2 else ""
                
                if not cls.startswith("03"):
                    continue
                
                # Extract vendor
                if pci_id.startswith("1002"):
                    vendor = "amd"
                elif pci_id.startswith("10de"):
                    vendor = "nvidia"
                elif pci_id.startswith("8086"):
                    vendor = "intel"
                else:
                    vendor = "unknown"
                
                if not any(g['vendor'] == vendor for g in gpus):
                    gpus.append({
                        'name': f"GPU ({vendor})",
                        'vendor': vendor,
                        'vram_bytes': 0,
                    })
    except Exception as e:
        logger.debug(f"Detector: PCI proc error: {e}")
    return gpus


def _detect_nvidia_via_smi(gpus: List[dict]):
    """Check for NVIDIA GPU presence via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                parts = line.split(',')
                name = parts[0].strip() if parts else "NVIDIA GPU"
                vram_mb = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 0
                vram_bytes = vram_mb * 1024 * 1024
                if not any(g['vendor'] == 'nvidia' for g in gpus):
                    gpus.append({
                        'name': name,
                        'vendor': 'nvidia',
                        'vram_bytes': vram_bytes,
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception as e:
        logger.debug(f"Detector: nvidia-smi error: {e}")


def _detect_gpu_via_lspci(gpus: List[dict]):
    """Last resort: parse lspci output for GPUs."""
    try:
        result = subprocess.run(
            ["lspci", "-nn"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'VGA' in line or '3D' in line or 'Display' in line:
                    vendor = 'unknown'
                    name = line.strip()
                    if '1002' in line or 'AMD' in line or 'Radeon' in line:
                        vendor = 'amd'
                    elif '10de' in line or 'NVIDIA' in line:
                        vendor = 'nvidia'
                    elif '8086' in line or 'Intel' in line:
                        vendor = 'intel'
                    
                    if not any(g['vendor'] == vendor for g in gpus):
                        gpus.append({
                            'name': name,
                            'vendor': vendor,
                            'vram_bytes': 0,
                        })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception as e:
        logger.debug(f"Detector: lspci error: {e}")


# -------------------- APU Detection --------------------

def is_apu_windows(gpu_name: str, vram_bytes: int) -> bool:
    """Detect if a Windows GPU is an APU/iGPU with shared memory.
    
    APU characteristics:
      - Name contains APU-related keywords
      - VRAM is suspiciously small (< 512MB dedicated)
    
    Returns True if the GPU appears to be an APU.
    """
    name_lower = gpu_name.lower()
    apu_keywords = [
        'radeon graphics', 'radeon™ graphics', 'radeon(tm) graphics',
        'radeon 6', 'radeon 7', 'radeon 8', 'radeon 9',
        'radeon veg', 'amd apu', 'accelerated processing unit',
        'intel(r) iris', 'intel(r) hd', 'intel(r) uhd',
        'intel arc', 'intel graphics',
    ]
    
    # Check name keywords
    if any(kw in name_lower for kw in apu_keywords):
        return True
    
    # Check VRAM: if it's < 512MB, it's likely an APU with shared memory
    # (Dedicated GPUs always have >= 1GB since ~2010)
    if 0 < vram_bytes < 512 * 1024 * 1024:
        return True
    
    # Check if vendor is Intel (almost always integrated)
    if 'intel' in name_lower and 'arc' not in name_lower:
        return True
    
    return False


def is_apu_linux(vendor: str, vram_bytes: int) -> bool:
    """Detect APU on Linux.
    
    Intel integrated GPUs are always APUs.
    AMD APUs typically have < 1GB dedicated VRAM or VRAM = 0 (shared).
    """
    if vendor == 'intel':
        return True
    if vendor == 'amd' and (vram_bytes == 0 or vram_bytes < 512 * 1024 * 1024):
        return True
    return False


# -------------------- Main API --------------------

def detect_hardware() -> dict:
    """Main detection function. Returns a dict with OS and GPU information.
    
    Returns:
        {
            'os': 'windows' | 'linux' | 'unknown',
            'gpus': [{'name': str, 'vendor': str, 'vram_bytes': int}, ...],
            'primary_vendor': 'amd' | 'nvidia' | 'intel' | 'unknown',
            'has_apu': bool,
        }
    """
    os_name = detect_os()
    
    if os_name == 'windows':
        gpus = detect_gpu_vendors_windows()
    elif os_name == 'linux':
        gpus = detect_gpu_vendors_linux()
    else:
        gpus = []
    
    # Determine primary vendor (first real GPU, prefer dGPU over iGPU)
    primary_vendor = 'unknown'
    for gpu in gpus:
        vendor = gpu.get('vendor', 'unknown')
        vram = gpu.get('vram_bytes', 0)
        # Prefer discrete GPUs (have VRAM > 512MB)
        if vendor in ('nvidia',) or (vendor in ('amd', 'intel') and vram > 512 * 1024 * 1024):
            primary_vendor = vendor
            break
    
    if primary_vendor == 'unknown' and gpus:
        primary_vendor = gpus[0].get('vendor', 'unknown')
    
    # Detect APUs
    has_apu = False
    for gpu in gpus:
        vendor = gpu.get('vendor', '')
        name = gpu.get('name', '')
        vram = gpu.get('vram_bytes', 0)
        if os_name == 'windows' and is_apu_windows(name, vram):
            has_apu = True
            break
        if os_name == 'linux' and is_apu_linux(vendor, vram):
            has_apu = True
            break
    
    result = {
        'os': os_name,
        'gpus': gpus,
        'primary_vendor': primary_vendor,
        'has_apu': has_apu,
        'gpu_count': len(gpus),
    }
    
    logger.info(f"Detector: {result}")
    return result