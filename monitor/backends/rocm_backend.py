"""
ROCM Backend - AMD GPU monitoring via HIP SDK tools
=====================================================
Uses the AMD HIP SDK (ROCm) installed on Windows to read GPU stats.
Zero external Python dependencies.

Primary tool: hipInfo.exe — provides static GPU properties
  (name, clock, memory, architecture)

Temperature/Fan: NOT available via HIP SDK alone.
  Requires amd-smi.exe which is part of full ROCm platform (not HIP SDK).
  If available, auto-detects and uses it.
"""

import logging
import os
import platform
import re
import subprocess

from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)


def _find_roc_bin() -> str | None:
    """Locate ROCm/HIP bin directory."""
    hip_path = os.environ.get("HIP_PATH", "")
    if hip_path:
        bin_dir = os.path.join(hip_path.rstrip("\\/"), "bin")
        if os.path.isdir(bin_dir):
            return bin_dir

    # Scan Program Files for ROCm installations
    base = r"C:\Program Files\AMD\ROCm"
    if os.path.isdir(base):
        for entry in os.listdir(base):
            bin_dir = os.path.join(base, entry, "bin")
            if os.path.isdir(bin_dir):
                return bin_dir
    return None


def _find_hipinfo() -> str | None:
    """Locate hipInfo.exe."""
    bin_dir = _find_roc_bin()
    if bin_dir:
        exe = os.path.join(bin_dir, "hipInfo.exe")
        if os.path.isfile(exe):
            return exe
    return None


def _find_amd_smi() -> str | None:
    """Locate amd-smi.exe if present."""
    bin_dir = _find_roc_bin()
    if bin_dir:
        exe = os.path.join(bin_dir, "amd-smi.exe")
        if os.path.isfile(exe):
            return exe
        # Also check for amd-smi-cli
        alt = os.path.join(bin_dir, "amd-smi-cli.exe")
        if os.path.isfile(alt):
            return alt
    return None


def _parse_hipinfo(output: str) -> dict:
    """Parse hipInfo.exe output into a dict."""
    info = {}
    info["gpu_name"] = ""
    info["clock_rate_mhz"] = 0
    info["memory_clock_rate_mhz"] = 0
    info["memory_total_gb"] = 0.0
    info["memory_total_mb"] = 0
    info["memory_bus_width"] = 0
    info["gcn_arch_name"] = ""
    info["arch_major"] = 0
    info["arch_minor"] = 0
    info["is_integrated"] = False

    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("Name:"):
            info["gpu_name"] = line.split(":", 1)[1].strip()
        elif line.startswith("clockRate:"):
            m = re.search(r"(\d+)", line)
            if m:
                info["clock_rate_mhz"] = int(m.group(1))
        elif line.startswith("memoryClockRate:"):
            m = re.search(r"(\d+)", line)
            if m:
                info["memory_clock_rate_mhz"] = int(m.group(1))
        elif line.startswith("totalGlobalMem:"):
            m = re.search(r"([\d.]+)\s*GB", line)
            if m:
                gb = float(m.group(1))
                info["memory_total_gb"] = gb
                info["memory_total_mb"] = int(gb * 1024)
        elif line.startswith("memoryBusWidth:"):
            m = re.search(r"(\d+)", line)
            if m:
                info["memory_bus_width"] = int(m.group(1))
        elif line.startswith("gcnArchName:"):
            info["gcn_arch_name"] = line.split(":", 1)[1].strip()
        elif line.startswith("major:"):
            m = re.search(r"(\d+)", line)
            if m:
                info["arch_major"] = int(m.group(1))
        elif line.startswith("minor:"):
            m = re.search(r"(\d+)", line)
            if m:
                info["arch_minor"] = int(m.group(1))
        elif line.startswith("isIntegrated:"):
            info["is_integrated"] = line.split(":", 1)[1].strip() == "1"

    return info


def _get_gpu_info() -> dict | None:
    """Get GPU info from hipInfo.exe. Returns dict or None."""
    exe = _find_hipinfo()
    if not exe:
        return None

    try:
        result = subprocess.run(
            [exe],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _parse_hipinfo(result.stdout)
    except Exception as e:
        logger.debug(f"ROCm hipInfo error: {e}")

    return None


def _read_sensors_via_amd_smi() -> tuple[float, int, float]:
    """Read temperature, fan, utilization via amd-smi.

    Returns: (temperature_c, fan_pct, utilization_pct)
    """
    exe = _find_amd_smi()
    if not exe:
        return 0.0, 0, 0.0

    temp = 0.0
    fan = 0
    util = 0.0

    try:
        # Try metric subcommand
        result = subprocess.run(
            [exe, "metric", "--gpu", "--csv"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        stdout = result.stdout.strip()
        if result.returncode == 0 and stdout:
            # Parse CSV output for temp/fan/util
            for line in stdout.split("\n"):
                lower = line.lower()
                if "temperature" in lower:
                    m = re.search(r"(\d+\.?\d*)", line)
                    if m:
                        val = float(m.group(1))
                        if 20 <= val <= 115:
                            temp = val
                elif "fan" in lower:
                    m = re.search(r"(\d+)", line)
                    if m:
                        val = int(m.group(1))
                        if 0 <= val <= 100:
                            fan = val
                elif "utilization" in lower or "gfx" in lower:
                    m = re.search(r"(\d+\.?\d*)", line)
                    if m:
                        val = float(m.group(1))
                        if 0 <= val <= 100:
                            util = val

            if temp > 0 or fan > 0:
                return temp, fan, util

        # Try static subcommand
        result2 = subprocess.run(
            [exe, "static", "--gpu"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        stdout2 = result2.stdout.strip()
        if result2.returncode == 0 and stdout2:
            for line in stdout2.split("\n"):
                lower = line.lower()
                if "temperature" in lower:
                    m = re.search(r"(\d+\.?\d*)", line)
                    if m:
                        val = float(m.group(1))
                        if 20 <= val <= 115:
                            temp = val

    except Exception as e:
        logger.debug(f"ROCm amd-smi error: {e}")

    return temp, fan, util


class ROCMBackend(MonitorBackend):
    """AMD GPU monitoring via ROCm/HIP SDK tools.

    Uses hipInfo.exe for static GPU properties (name, clock, memory).
    Can use amd-smi.exe for temperature/fan if available.

    Falls back to PDH counters via base monitor for VRAM/utilization.
    """

    name = "rocm"

    def __init__(self):
        super().__init__()
        self._hipinfo = None
        self._has_amd_smi = False
        self._gpu_info_cache = None

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            logger.debug("ROCm backend: Windows only")
            return False

        exe = _find_hipinfo()
        if not exe:
            logger.debug("ROCm backend: hipInfo.exe not found")
            return False

        self._hipinfo = exe
        logger.info(f"ROCm backend: using hipInfo at {exe}")

        # Check for amd-smi
        smi = _find_amd_smi()
        if smi:
            self._has_amd_smi = True
            logger.info(f"ROCm backend: amd-smi available at {smi}")

        # Cache GPU info
        self._gpu_info_cache = _get_gpu_info()
        if not self._gpu_info_cache:
            return False

        self.available = True
        self.vendor = "amd"
        self.gpu_count = 1
        self.gpu_names = [self._gpu_info_cache.get("gpu_name", "AMD GPU")]
        return True

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        stats = AMDGPUStats(
            gpu_id=gpu_id,
            gpu_name=self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else "AMD GPU",
            is_available=True,
            vendor="amd",
            driver="rocm",
        )

        # Static info from cache
        if self._gpu_info_cache:
            info = self._gpu_info_cache
            stats.gpu_name = info.get("gpu_name", stats.gpu_name)
            stats.core_clock = info.get("clock_rate_mhz", 0)
            stats.memory_total = info.get("memory_total_mb", 0) * 1024 * 1024  # MB -> bytes
            stats.is_apu = info.get("is_integrated", False)

        # Sensor data - only from amd-smi if available
        if self._has_amd_smi:
            temp, fan, util = _read_sensors_via_amd_smi()
            stats.temperature = temp
            stats.fan_speed = fan
            stats.utilization_gpu = util

        # Fallback: get live VRAM usage + utilization from PDH counters
        # (hipInfo only gives static total VRAM, PDH gives live usage)
        try:
            from .pdh_backend import PDHBackend
            pdh = PDHBackend()
            if pdh.initialize():
                pdh_stats = pdh.get_stats(gpu_id)
                if pdh_stats.memory_used > 0:
                    stats.memory_used = pdh_stats.memory_used
                if pdh_stats.memory_total > 0 and stats.memory_total == 0:
                    stats.memory_total = pdh_stats.memory_total
                if pdh_stats.utilization_gpu > 0:
                    stats.utilization_gpu = pdh_stats.utilization_gpu
                if pdh_stats.temperature > 0 and stats.temperature == 0:
                    stats.temperature = pdh_stats.temperature
                if pdh_stats.memory_clock > 0:
                    stats.memory_clock = pdh_stats.memory_clock
        except Exception:
            pass

        return stats
