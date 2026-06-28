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
from typing import Optional, List

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
        self._cached_fan: Optional[int] = None   # None => not yet sampled
        self._fan_cache_timestamp: float = 0
        self._TEMP_CACHE_SECONDS = 2.0
        self._FAN_CACHE_SECONDS = 1.0

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
                except (OSError, ValueError) as e:
                    logger.debug(f"Linux AMD: BDF lookup failed: {e}")

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
                        except (OSError, ValueError) as e:
                            logger.debug(f"Linux AMD: hwmon driver name read failed: {e}")

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
        except (OSError, ValueError) as e:
            logger.debug(f"Linux AMD: system RAM read failed: {e}")
            self._system_ram_total = 8 * 1024 * 1024 * 1024  # 8GB fallback

    def _read_sysfs(self, path: str) -> Optional[str]:
        """Safely read a sysfs file."""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return f.read().strip()
        except (OSError, ValueError) as e:
            logger.debug(f"Linux AMD: sysfs read failed for {path}: {e}")
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
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Linux AMD: pp_dpm_sclk parse failed: {e}")

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
        """Read GPU temperature from hwmon with caching.

        Sensor priority (highest wins):

          1. ``temp*_label == 'junction'`` — GPU die temp, the value AMD
             Radeon Software and HWiNFO report as "GPU Temperature".
             Best signal for thermal throttling on RDNA3.
          2. ``temp*_label == 'edge'`` — case edge temp, the conservative
             number most users see when they touch the backplate.
          3. Fallback: max of all ``temp*_input`` files within 20–120°C.
        """
        now = time.time()
        if now - self._temp_cache_timestamp < self._TEMP_CACHE_SECONDS:
            return self._cached_temp

        junction = None
        edge = None
        fallback_max = 0.0
        for hwmon_path in self._hwmon_paths:
            try:
                for entry in sorted(os.listdir(hwmon_path)):
                    if not (entry.startswith("temp") and entry.endswith("_input")):
                        continue
                    temp_file = os.path.join(hwmon_path, entry)
                    label_file = temp_file.replace("_input", "_label")
                    try:
                        with open(temp_file, 'r') as f:
                            raw = int(f.read().strip())
                    except (ValueError, OSError):
                        continue
                    celsius = raw / 1000.0
                    if not (20 <= celsius <= 120):
                        continue
                    if celsius > fallback_max:
                        fallback_max = celsius
                    label = ""
                    if os.path.exists(label_file):
                        try:
                            with open(label_file, 'r') as f:
                                label = f.read().strip().lower()
                        except OSError:
                            pass
                    if label == "junction" and (junction is None or celsius > junction):
                        junction = celsius
                    elif label == "edge" and (edge is None or celsius > edge):
                        edge = celsius
            except OSError as e:
                logger.debug(f"Linux AMD: hwmon listdir failed for {hwmon_path}: {e}")

        temp = junction if junction is not None else (edge if edge is not None else fallback_max)
        self._cached_temp = temp
        self._temp_cache_timestamp = now
        return temp

    def _get_fan_speed(self) -> int:
        """Read fan duty cycle (%) from amdgpu hwmon.

        Strategy chain — first hit wins, each card path is tried in order:

          1. ``pwm1`` / ``pwm1_max`` — raw PWM duty (legacy pre-6.x driver,
             also some aftermarket drivers).
          2. ``fan1_target`` / ``fan1_max`` — **firmware-intended RPM** /
             max RPM. This is the most useful value on RDNA3 (Navi 32,
             RX 7700/7800 XT) when the kernel driver has *stopped* the fan
             at idle: ``fan1_input`` reports 0 RPM (the fan really is
             stopped) but ``fan1_target`` shows what the firmware would
             command the moment temperature rises. Reporting the target
             avoids the "stuck at 0%" false reading.
          3. ``fan1_input`` / ``fan1_max`` — current RPM scaled to %.
             Pre-RDNA3 fallback; on modern driver the input is 0 in
             zero-RPM idle and this returns 0.
          4. ``fan1_input`` permille (raw // 10) — older drivers that
             report duty as 0–1000 instead of RPM.

        Result is clamped to [0, 100] and cached for 5s like temperature
        to keep sysfs reads light.

        Card without fan control (``pwm1_enable == "0"`` AND no
        ``fan1_*`` files) returns 0 — passive / fanless designs shouldn't
        pretend to have a fan.
        """
        now = time.time()
        # Independent cache window — fan can change much faster than
        # temp during a workload ramp, so sharing temp's 5s window made
        # the overlay look "stuck" at the boot-time reading.
        cached = getattr(self, "_cached_fan", None)
        if (
            cached is not None
            and now - self._fan_cache_timestamp < self._FAN_CACHE_SECONDS
        ):
            return cached

        fan_pct = 0
        for hwmon_path in self._hwmon_paths:
            # If the driver exposes pwm1_enable == 0 (manual off) AND no
            # fan1_* files, the card is fanless — skip the whole path.
            enable_file = os.path.join(hwmon_path, "pwm1_enable")
            has_pwm1 = os.path.exists(os.path.join(hwmon_path, "pwm1"))
            has_fan1 = os.path.exists(os.path.join(hwmon_path, "fan1_input"))
            if not (has_pwm1 or has_fan1):
                continue

            pwm_disabled = False
            if os.path.exists(enable_file):
                try:
                    with open(enable_file, 'r') as f:
                        if f.read().strip() == "0":
                            pwm_disabled = True
                except OSError:
                    pass

            # === Strategy 1: pwm1 / pwm1_max (raw duty, legacy) ===
            logger.debug(f"FAN: hwmon={hwmon_path} has_pwm1={has_pwm1} pwm_disabled={pwm_disabled} pwm1_enable_file={os.path.exists(enable_file)}")
            if not pwm_disabled and has_pwm1:
                pwm_file = os.path.join(hwmon_path, "pwm1")
                pwm_max_file = os.path.join(hwmon_path, "pwm1_max")
                logger.debug(f"FAN: Strategy1 checking {pwm_file} exists={os.path.exists(pwm_file)} max_exists={os.path.exists(pwm_max_file)}")
                if os.path.exists(pwm_max_file):
                    try:
                        with open(pwm_file, 'r') as f:
                            pwm = int(f.read().strip())
                        with open(pwm_max_file, 'r') as f:
                            pwm_max = int(f.read().strip())
                        logger.debug(f"FAN: Strategy1 pwm={pwm} pwm_max={pwm_max}")
                        if pwm_max > 0:
                            pct = int(round(pwm * 100.0 / pwm_max))
                            logger.debug(f"FAN: Strategy1 pct={pct}")
                            fan_pct = max(fan_pct, pct)
                            if pct > 0:
                                # Got a real reading — stop walking backends.
                                break
                    except (ValueError, OSError) as e:
                        logger.debug(f"FAN: Strategy1 exception: {e}")

            # === Strategy 2: fan1_target / fan1_max (firmware intent) ===
            # On modern RDNA3 drivers, this is the *only* way to see fan
            # activity before the fan actually spins up — fan1_input stays
            # at 0 RPM in zero-RPM idle, so a naive implementation reports
            # "0%" the whole time. fan1_target reflects what the firmware
            # would command once temperature crosses the ramp threshold.
            target_file = os.path.join(hwmon_path, "fan1_target")
            max_file = os.path.join(hwmon_path, "fan1_max")
            if os.path.exists(target_file) and os.path.exists(max_file):
                try:
                    with open(target_file, 'r') as f:
                        target = int(f.read().strip())
                    with open(max_file, 'r') as f:
                        fan_max = int(f.read().strip())
                    if fan_max > 0 and target > 0:
                        pct = int(round(target * 100.0 / fan_max))
                        fan_pct = max(fan_pct, pct)
                        # Keep walking — Strategy 3 may still report a
                        # higher RPM-derived value while fan is spinning.
                except (ValueError, OSError):
                    pass

            # === Strategy 3: fan1_input / fan1_max (current RPM scaled) ===
            # Modern RDNA3 only — older drivers used a different file.
            if has_fan1 and os.path.exists(max_file):
                try:
                    with open(os.path.join(hwmon_path, "fan1_input"), 'r') as f:
                        rpm = int(f.read().strip())
                    if rpm > 0:
                        with open(max_file, 'r') as f:
                            fan_max = int(f.read().strip())
                        if fan_max > 0:
                            fan_pct = max(fan_pct, int(round(rpm * 100.0 / fan_max)))
                except (ValueError, OSError):
                    pass

            # === Strategy 4: fan1_input permille (legacy 0–1000 driver) ===
            # Older out-of-tree drivers reported fan duty as 0–1000
            # permille instead of RPM. Modern drivers report RPM (often
            # > 1000 even at low speeds) and were already handled by
            # Strategy 3; here we only act on values that *can't* be
            # RPM. Upper bound 1000 means "if RPM is reported, it would
            # be at least 1001" — false on most cards but cheap to guard.
            if has_fan1:
                try:
                    with open(os.path.join(hwmon_path, "fan1_input"), 'r') as f:
                        raw = int(f.read().strip())
                    # permille on legacy drivers: 778 = 77.8% duty.
                    if 11 < raw <= 1000 and raw != int(open(os.path.join(hwmon_path, "fan1_max")).read().strip()):
                        # Last guard: skip if this value happens to equal
                        # fan1_max (some quirky firmware reports max as
                        # input when at full tilt).
                        fan_pct = max(fan_pct, raw // 10)
                except (ValueError, OSError):
                    pass

            if fan_pct > 0:
                break

        fan_pct = max(0, min(100, fan_pct))
        self._cached_fan = fan_pct
        self._fan_cache_timestamp = time.time()
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