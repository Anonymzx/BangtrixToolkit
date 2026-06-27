"""
Linux AMD GPU Backend
=====================
Reads GPU stats from Linux sysfs (/sys/class/drm/) and hwmon for AMD GPUs.
Zero external dependencies — uses standard library only.

Data sources:
  - GPU utilization: /sys/class/drm/card*/device/gpu_busy_percent
  - VRAM: /sys/class/drm/card*/device/mem_info_vram_total
           /sys/class/drm/card*/device/mem_info_vram_used
  - Temperature: /sys/class/drm/card*/device/hwmon/hwmon*/temp1_input
  - Core clock: /sys/class/drm/card*/device/pp_dpm_sclk (average from PP table)
  - Power: /sys/class/drm/card*/device/hwmon/hwmon*/power1_average
  - Product name: ``lspci -mm`` (sysfs does NOT expose a human-readable name
    for most consumer AMD GPUs — this is the only reliable source without
    requiring a userspace tool like rocminfo.)

APU Support:
  - APUs with shared memory: memory_total=0, memory_shared=system_RAM
  - Detects APU by checking VRAM size < 512MB
"""

import logging
import os
import re
import subprocess
import time
from typing import Optional

from .base import MonitorBackend, HardwareStats

logger = logging.getLogger(__name__)


def _read_product_name_from_lspci(pci_slot: str) -> Optional[str]:
    """Look up the human-readable product name for a PCI slot via ``lspci -mm``.

    sysfs exposes ``vendor`` / ``device`` IDs (e.g. ``1002:747e``) but no
    product string for most consumer AMD GPUs. ``lspci -mm`` gives us a
    machine-readable ``"VGA compatible controller"  "Vendor"  "Product Name"``
    tuple that's easy to parse. Falls back to ``None`` when lspci is
    unavailable or doesn't know the device.
    """
    try:
        result = subprocess.run(
            ["lspci", "-mm", "-s", pci_slot],
            capture_output=True, text=True, timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    except Exception as e:
        logger.debug(f"lspci lookup failed for {pci_slot}: {e}")
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    # Example output:
    #   03:00.0 "VGA" "Advanced Micro Devices, Inc. [AMD/ATI]" "Navi 32 [Radeon RX 7700 XT / 7800 XT]" ...
    # Quoted fields; we want field index 2 (the product name).
    parts = re.findall(r'"([^"]*)"', result.stdout)
    if len(parts) >= 3:
        product = parts[2].strip()
        # Strip "AMD/ATI" / "[AMD/ATI]" style vendor tags that lspci sometimes
        # leaves in the product string on older versions.
        product = re.sub(r"\[?AMD/ATI\]?\s*", "", product).strip()
        # Strip "Navi N" / "Navi NN" silicon code prefix when a marketing
        # name is present — the marketing name is more user-friendly.
        m = re.search(r"\[(Radeon[^\]]+)\]", product)
        if m:
            return m.group(1).strip()
        return product or None
    return None


class LinuxAMDGPUBackend(MonitorBackend):
    """AMD GPU monitoring on Linux via sysfs + hwmon"""
    name = "linux-amdgpu-sysfs"

    def __init__(self):
        super().__init__()
        self.vendor = "amd"
        self._card_paths: list[str] = []
        self._pci_slots: list[str] = []   # PCI BDF per card (e.g. "0000:03:00.0")
        self._vram_total: int = 0
        self._is_apu: bool = False
        self._system_ram_total: int = 0
        self._hwmon_paths: list[str] = []
        self._temp_cache_timestamp: float = 0
        self._cached_temp: float = 0.0
        self._TEMP_CACHE_SECONDS = 5.0

    def initialize(self) -> bool:
        import platform
        if platform.system().lower() != "linux":
            return False

        try:
            self._find_amd_cards()
            if not self._card_paths:
                return False

            self._detect_vram()
            self._detect_hwmon()
            self._detect_system_ram()
            self._resolve_product_names()

            self.gpu_count = len(self._card_paths)
            self.gpu_names = [
                n if n else f"AMD GPU {i}"
                for i, n in enumerate(self._product_names)
            ] or [f"AMD GPU {i}" for i in range(self.gpu_count)]
            self.available = True

            logger.info(
                f"Linux AMD: {self.gpu_count} GPU(s), "
                f"names={self.gpu_names}, "
                f"VRAM={self._vram_total / (1024*1024):.0f}MB, "
                f"APU={self._is_apu}"
            )
            return True
        except Exception as e:
            logger.error(f"Linux AMD init error: {e}")
            return False

    def _find_amd_cards(self):
        """Find AMD GPU card directories in /sys/class/drm/"""
        drm_path = "/sys/class/drm"
        if not os.path.exists(drm_path):
            return

        # Match a PCI BDF anywhere in the path, e.g. "0000:03:00.0".
        # The card's device symlink points into
        # /sys/devices/pci.../BBBB:BB:BB.B/drm/cardN, so the *last* BDF in
        # the path is the leaf GPU device — root bridges upstream appear
        # earlier and would confuse lspci's -s match.
        bdf_re = re.compile(r"([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.\d+)")

        for entry in sorted(os.listdir(drm_path)):
            if not entry.startswith("card") or "-" in entry:
                continue

            card_path = os.path.join(drm_path, entry)

            # Check vendor
            vendor_file = os.path.join(card_path, "device", "vendor")
            if os.path.exists(vendor_file):
                try:
                    with open(vendor_file, 'r') as f:
                        vendor_id = f.read().strip().lower()
                    if '1002' in vendor_id or 'amd' in vendor_id:
                        self._card_paths.append(card_path)
                        # The device symlink resolves to something like
                        # /sys/devices/pci0000:00/.../0000:03:00.0/drm/cardN
                        # — pull the leaf PCI BDF out of it.
                        real = os.path.realpath(card_path)
                        matches = bdf_re.findall(real)
                        self._pci_slots.append(matches[-1] if matches else "")
                except Exception:
                    pass

            # Fallback: check for amdgpu driver
            if not self._card_paths or card_path != self._card_paths[-1]:
                if os.path.exists(os.path.join(card_path, "device", "gpu_busy_percent")):
                    if card_path not in self._card_paths:
                        self._card_paths.append(card_path)
                        real = os.path.realpath(card_path)
                        matches = bdf_re.findall(real)
                        self._pci_slots.append(matches[-1] if matches else "")

    def _resolve_product_names(self):
        """Populate ``self._product_names`` via ``lspci -mm``.

        sysfs exposes only PCI vendor/device IDs (e.g. ``1002:747e``) but no
        human-readable product string for consumer AMD GPUs. We fall back to
        ``lspci`` to recover something like ``"Radeon RX 7800 XT"``.

        Emits a single WARNING if lspci returns nothing for any GPU — the
        overlay will fall back to "AMD GPU N" placeholders, and the user
        should know why instead of staring at a generic widget.
        """
        self._product_names = []
        lspci_missing_count = 0
        for slot in self._pci_slots:
            name = _read_product_name_from_lspci(slot) if slot else None
            # Normalize the lspci BDF "0000:03:00.0" into the "-s" argument
            # form "03:00.0" if needed. lspci accepts both.
            if not name and slot:
                short = re.sub(r"^[0-9a-fA-F]{4}:", "", slot)
                name = _read_product_name_from_lspci(short)
            if not name:
                lspci_missing_count += 1
            self._product_names.append(name)

        if lspci_missing_count == len(self._pci_slots) and self._pci_slots:
            # ALL GPUs missing — likely lspci is not installed.
            logger.warning(
                "Linux AMD: lspci is unavailable; install 'pciutils' to "
                "display real GPU product names instead of 'AMD GPU N'."
            )
        elif lspci_missing_count > 0:
            logger.warning(
                f"Linux AMD: lspci did not resolve names for "
                f"{lspci_missing_count}/{len(self._pci_slots)} GPU(s)"
            )
        else:
            logger.debug(f"Linux AMD: resolved product names: {self._product_names}")

    def _detect_vram(self):
        """Read VRAM total from sysfs. Detect APU shared memory."""
        vram_total = 0
        for card_path in self._card_paths:
            vram_file = os.path.join(card_path, "device", "mem_info_vram_total")
            if os.path.exists(vram_file):
                try:
                    with open(vram_file, 'r') as f:
                        val = int(f.read().strip())
                    if val > vram_total:
                        vram_total = val
                except (ValueError, OSError):
                    pass

        self._vram_total = vram_total

        # APU detection: < 512MB VRAM means shared memory
        if 0 < vram_total < 512 * 1024 * 1024:
            self._is_apu = True
            self._vram_total = vram_total  # Keep actual value, even if small
        elif vram_total == 0:
            self._is_apu = True  # Likely APU with no dedicated VRAM reporting

    def _detect_hwmon(self):
        """Find hwmon paths for AMD GPU temperatures.

        Logs a one-shot WARNING if no amdgpu hwmon device is found —
        without it the overlay will show ``N/A`` for temperature and the
        user is left guessing why (most common cause: missing
        ``amdgpu`` kernel module or insufficient permissions on
        ``/sys/class/drm/card*/device/hwmon``).
        """
        for card_path in self._card_paths:
            hwmon_dir = os.path.join(card_path, "device", "hwmon")
            if os.path.exists(hwmon_dir):
                for hwmon_entry in os.listdir(hwmon_dir):
                    hwmon_path = os.path.join(hwmon_dir, hwmon_entry)
                    name_file = os.path.join(hwmon_path, "name")
                    if os.path.exists(name_file):
                        try:
                            with open(name_file, 'r') as f:
                                name = f.read().strip().lower()
                            if 'amdgpu' in name:
                                self._hwmon_paths.append(hwmon_path)
                        except Exception:
                            pass

        if self._card_paths and not self._hwmon_paths:
            logger.warning(
                "Linux AMD: no amdgpu hwmon device found — temperature "
                "and power readings will be N/A (check that the amdgpu "
                "kernel module is loaded and hwmon is readable)."
            )

    def _detect_system_ram(self):
        """Read total system RAM for APU shared memory tracking."""
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        parts = line.split()
                        if len(parts) >= 2:
                            self._system_ram_total = int(parts[1]) * 1024
                        break
        except Exception:
            self._system_ram_total = 8 * 1024 * 1024 * 1024  # 8GB fallback

    def _read_sysfs(self, path: str) -> Optional[str]:
        """Safely read a sysfs file."""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        return None

    def get_stats(self, gpu_id: int = 0) -> HardwareStats:
        try:
            if gpu_id >= len(self._card_paths):
                return HardwareStats(
                    gpu_id=gpu_id,
                    vendor="amd",
                    is_available=False,
                    error_message=f"GPU {gpu_id} not found",
                )

            card_path = self._card_paths[gpu_id]
            name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}"

            stats = HardwareStats(
                gpu_id=gpu_id,
                gpu_name=name,
                vendor="amd",
                driver="amdgpu-sysfs",
                is_apu=self._is_apu,
                is_available=True,
            )

            # GPU Utilization (%)
            util_val = self._read_sysfs(os.path.join(card_path, "device", "gpu_busy_percent"))
            if util_val:
                try:
                    stats.utilization_gpu = min(100.0, max(0.0, float(util_val)))
                except ValueError:
                    pass

            # VRAM
            vram_used_file = os.path.join(card_path, "device", "mem_info_vram_used")
            vram_used = self._read_sysfs(vram_used_file)
            if vram_used and self._vram_total > 0:
                try:
                    used = int(vram_used)
                    stats.memory_used = used
                    stats.memory_total = self._vram_total
                    stats.memory_free = max(0, self._vram_total - used)
                    if self._vram_total > 0:
                        stats.utilization_memory = (used / self._vram_total) * 100.0
                except ValueError:
                    pass

            # APU shared memory fallback
            if self._is_apu and stats.memory_total == 0:
                try:
                    import psutil
                    svmem = psutil.virtual_memory()
                    stats.memory_shared = self._system_ram_total
                    stats.memory_used = int(svmem.used * 0.25)  # Estimate GPU portion
                    stats.utilization_memory = svmem.percent
                except ImportError:
                    stats.memory_shared = self._system_ram_total

            # Temperature (cached)
            stats.temperature = self._get_temperature()

            # Fan speed (RPM -> duty %)
            stats.fan_speed = self._get_fan_speed()

            # Core Clock
            clock_val = self._read_sysfs(os.path.join(card_path, "device", "pp_dpm_sclk"))
            if clock_val:
                try:
                    # Parse average clock from PP table
                    lines = clock_val.strip().split('\n')
                    for line in lines:
                        if 'Mhz' in line or 'MHz' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                # Extract number before MHz
                                import re
                                match = re.search(r'(\d+)\s*Mhz', parts[-1], re.IGNORECASE)
                                if match:
                                    stats.core_clock = int(match.group(1))
                                    break
                except Exception:
                    pass

            # Power draw
            power = self._read_power(card_path)
            if power is not None:
                stats.power_draw = power

            return stats

        except Exception as e:
            logger.error(f"Linux AMD get_stats({gpu_id}) error: {e}")
            return HardwareStats(
                gpu_id=gpu_id,
                vendor="amd",
                is_available=False,
                error_message=str(e),
            )

    def _get_temperature(self) -> float:
        """Read GPU temperature from hwmon with caching."""
        now = time.time()
        if now - self._temp_cache_timestamp < self._TEMP_CACHE_SECONDS:
            return self._cached_temp

        temp = 0.0
        for hwmon_path in self._hwmon_paths:
            try:
                for entry in sorted(os.listdir(hwmon_path)):
                    if entry.startswith("temp") and entry.endswith("_input"):
                        temp_file = os.path.join(hwmon_path, entry)
                        try:
                            with open(temp_file, 'r') as f:
                                raw = int(f.read().strip())
                            celsius = raw / 1000.0
                            if 20 <= celsius <= 120:
                                if celsius > temp:
                                    temp = celsius
                        except (ValueError, OSError):
                            pass
            except Exception:
                pass

        self._cached_temp = temp
        self._temp_cache_timestamp = now
        return temp

    def _get_fan_speed(self) -> int:
        """Read fan duty cycle (%) from amdgpu hwmon.

        Strategy (in priority order):
          1. ``fan1_input`` is reported as a percentage-per-mille (e.g. ``778``
             = 77.8% duty). On modern drivers (>= 6.x) this is the most
             reliable source.
          2. ``pwm1`` / ``pwm1_max`` gives raw PWM duty — convert to %.
             Used when fan1_input isn't exposed (older drivers).

        The reported value matches what tools like ``radeontop`` /
        ``amdgpu-fan`` show. Some RDNA1 GPUs don't expose either
        (``pwm1_enable == 0`` = no fan control); we silently return 0 in
        that case — passive / fanless designs shouldn't pretend to
        have a fan.

        Result is clamped to [0, 100] and cached for 5s like temperature
        to keep sysfs reads light.
        """
        now = time.time()
        # Reuse the temp cache window — fan and temp are usually
        # sampled together and 5s is more than fresh enough. We only
        # return a cached value once we've actually populated one,
        # otherwise we'd permanently return 0 on a fresh backend.
        cached = getattr(self, "_cached_fan", None)
        if (
            cached is not None
            and now - self._temp_cache_timestamp < self._TEMP_CACHE_SECONDS
        ):
            return cached

        fan_pct = 0
        for hwmon_path in self._hwmon_paths:
            # Skip hwmon devices where the driver has disabled fan
            # control (pwm1_enable == 0) — reading still works but
            # value is meaningless.
            enable_file = os.path.join(hwmon_path, "pwm1_enable")
            if os.path.exists(enable_file):
                try:
                    with open(enable_file, 'r') as f:
                        if f.read().strip() == "0":
                            continue
                except OSError:
                    pass

            fan_input = os.path.join(hwmon_path, "fan1_input")
            if os.path.exists(fan_input):
                try:
                    with open(fan_input, 'r') as f:
                        raw = int(f.read().strip())
                    # fan1_input is RPM on some drivers and permille
                    # on others. Heuristic: > 10000 is clearly RPM,
                    # divide by 100 to get duty%.
                    if raw > 10000:
                        fan_pct = max(fan_pct, raw // 100)
                    else:
                        fan_pct = max(fan_pct, raw // 10)
                    if fan_pct:
                        break
                except (ValueError, OSError):
                    pass

            # Fallback to pwm1 / pwm1_max
            pwm_file = os.path.join(hwmon_path, "pwm1")
            pwm_max_file = os.path.join(hwmon_path, "pwm1_max")
            if os.path.exists(pwm_file) and os.path.exists(pwm_max_file):
                try:
                    with open(pwm_file, 'r') as f:
                        pwm = int(f.read().strip())
                    with open(pwm_max_file, 'r') as f:
                        pwm_max = int(f.read().strip())
                    if pwm_max > 0:
                        pct = int(round(pwm * 100.0 / pwm_max))
                        fan_pct = max(fan_pct, pct)
                        if fan_pct:
                            break
                except (ValueError, OSError):
                    pass

        fan_pct = max(0, min(100, fan_pct))
        self._cached_fan = fan_pct
        return fan_pct

    def _read_power(self, card_path: str) -> Optional[float]:
        """Read GPU power draw from hwmon."""
        for hwmon_path in self._hwmon_paths:
            try:
                power_file = os.path.join(hwmon_path, "power1_average")
                if os.path.exists(power_file):
                    with open(power_file, 'r') as f:
                        raw = int(f.read().strip())
                    # Convert microwatts to watts
                    return raw / 1_000_000.0
            except (ValueError, OSError):
                pass
        return None

    def close(self):
        pass