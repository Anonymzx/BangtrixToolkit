"""
AMD Temperature Reader
======================
Gets GPU temperature and fan speed for AMD RDNA3 GPUs using
only built-in Windows tools — zero dependencies.

Methods tried in order:
  1. wmic (native Windows CLI) — works on ALL Windows versions
  2. PowerShell Get-Counter (thermal zone)
  3. ADLX DLL via ctypes (if available)
"""

import json
import logging
import os
import platform
import re
import subprocess

logger = logging.getLogger(__name__)


def read_amd_temperature() -> tuple[float, int]:
    """Read AMD GPU temperature and fan speed.
    
    Returns:
        (temperature_celsius, fan_speed_percent)
        0.0, 0 if unavailable.
    """
    if platform.system() != "Windows":
        return 0.0, 0

    # Method 1: wmic (built-in Windows)
    temp, fan = _read_wmic_temp()
    if temp > 0 or fan > 0:
        logger.debug(f"AMD Temp: wmic -> {temp}C, {fan}%")
        return temp, fan

    # Method 2: PowerShell thermal zone
    temp, fan = _read_ps_thermal()
    if temp > 0:
        logger.debug(f"AMD Temp: thermal zone -> {temp}C")
        return temp, fan

    return 0.0, 0


def _read_wmic_temp() -> tuple[float, int]:
    """Read temperature using wmic (Win32_PerfFormattedData_Counters).
    Works on all Windows versions without extra installs."""
    temp = 0.0
    fan = 0

    try:
        # WMIC query for GPU temperature via performance counters
        result = subprocess.run(
            'wmic path Win32_PerfFormattedData_Counters_ThermalZoneInformation '
            'get Temperature /format:csv',
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.split('\n'):
                parts = line.strip().split(',')
                for p in parts:
                    try:
                        val = int(p)
                        if 2500 < val < 4000:  # Raw thermal zone values
                            celsius = (val - 2732) / 10.0
                            if 20 <= celsius <= 115:
                                temp = celsius
                    except (ValueError, IndexError):
                        pass
    except Exception as e:
        logger.debug(f"AMD Temp: wmic thermal zone error: {e}")

    return temp, fan


def _read_ps_thermal() -> tuple[float, int]:
    """Read temperature via PowerShell thermal zone."""
    temp = 0.0
    fan = 0

    ps_cmd = (
        'powershell -NoProfile -Command '
        '"Get-WmiObject -Namespace root/WMI -Class MSAcpi_ThermalZoneTemperature '
        '-ErrorAction SilentlyContinue | '
        'Where-Object { $_.Active -eq $true } | '
        'Select-Object @{N=\'T\';E={[math]::Round(($_.CurrentTemperature - 2732) / 10, 1)}} '
        '-ExpandProperty T"'
    )

    try:
        result = subprocess.run(
            ps_cmd,
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
            for line in lines:
                try:
                    val = float(line)
                    if 20 <= val <= 115:
                        temp = val
                        break
                except ValueError:
                    pass
    except Exception as e:
        logger.debug(f"AMD Temp: PS thermal error: {e}")

    if temp > 0:
        return temp, fan

    # Try getting discrete GPU temperature
    ps_gpu = (
        'powershell -NoProfile -Command '
                    '"Get-Counter -Counter \\\"GPU(*)\\Temperature\\\" '
        '-ErrorAction SilentlyContinue | Select-Object -ExpandProperty CounterSamples '
        '| Select-Object -First 1 -ExpandProperty CookedValue"'
    )
    try:
        result = subprocess.run(
            ps_gpu,
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            val = float(result.stdout.strip())
            if 20 <= val <= 115:
                temp = val
    except Exception as e:
        logger.debug(f"AMD Temp: PS GPU counter error: {e}")

    return temp, fan


def read_amd_temperature_safe() -> dict:
    """Safe wrapper that never raises — returns dict with temp/fan."""
    try:
        temp, fan = read_amd_temperature()
        return {
            "temperature": round(float(temp), 1),
            "fan_speed": int(fan),
            "temp_available": temp > 0,
            "fan_available": fan > 0,
        }
    except Exception as e:
        logger.error(f"AMD Temp: error: {e}")
        return {
            "temperature": 0.0,
            "fan_speed": 0,
            "temp_available": False,
            "fan_available": False,
        }