"""
LibreHardwareMonitor Backend
============================
Integrates LibreHardwareMonitor (LHM) for full GPU telemetry.
- Auto-detects if LHM is running via WMI
- Auto-downloads LHM portable if not present
- Auto-launches LHM as Administrator (via PowerShell Start-Process -Verb RunAs)
- Reads: Temperature, Fan Speed, GPU Load, VRAM, Clocks, Power
"""

import logging
import subprocess
import platform
import os
import json
import urllib.request
import zipfile

from .base import MonitorBackend, AMDGPUStats

logger = logging.getLogger(__name__)

LHM_DOWNLOAD_URL = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor.NET.10.zip"


class LibreHardwareBackend(MonitorBackend):
    name = "libre-hardware-monitor"

    def __init__(self):
        super().__init__()
        self._lhm_exe = None
        self._auto_launched = False

    def initialize(self) -> bool:
        if platform.system() != "Windows":
            return False

        # Check if LHM/OHM sensors are accessible via WMI
        if self._detect_wmi_sensors():
            logger.info("LHM Backend: detected running instance via WMI")
            self.available = True
            self.gpu_count = 1
            self.gpu_names = ["AMD GPU (LHM)"]
            return True

        # Download LHM if missing
        self._ensure_downloaded()

        # Try to auto-launch LHM as Administrator
        if self._lhm_exe and os.path.exists(self._lhm_exe):
            if self._auto_launch_lhm():
                # Wait a moment for WMI to register, then re-check
                import time
                time.sleep(2)
                if self._detect_wmi_sensors():
                    logger.info("LHM Backend: auto-launch succeeded via WMI")
                    self.available = True
                    self.gpu_count = 1
                    self.gpu_names = ["AMD GPU (LHM)"]
                    self._auto_launched = True
                    return True
                else:
                    logger.info(
                        "LHM Backend: downloaded but auto-launch failed. "
                        "Try running manually as Admin:\n"
                        f"  {self._lhm_exe} --wmi\n"
                        "Or double-click the 'start_lhm.bat' file."
                    )
            else:
                logger.info(
                    "LHM Backend: downloaded but not running. "
                    "Run as Admin:\n"
                    f"  {self._lhm_exe} --wmi"
                )

        return False

    def _get_lhm_dir(self) -> str:
        """LHM storage directory"""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "libre_hardware_monitor")

    def _detect_wmi_sensors(self) -> bool:
        """Check via PowerShell if LHM/OHM WMI sensors exist"""
        namespaces = ['root/LibreHardwareMonitor', 'root/OpenHardwareMonitor']
        for ns in namespaces:
            try:
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    f"Get-WmiObject -Namespace '{ns}' -Class Sensor "
                    f"2>$null | Select-Object -First 1 | ConvertTo-Json"
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0 and result.stdout.strip() and 'null' not in result.stdout:
                    return True
            except:
                pass
        return False

    def _ensure_downloaded(self):
        """Download LHM portable if not already present"""
        lhm_dir = self._get_lhm_dir()
        os.makedirs(lhm_dir, exist_ok=True)

        # Find existing exe
        for root, dirs, files in os.walk(lhm_dir):
            for f in files:
                if f.lower() == "librehardwaremonitor.exe":
                    self._lhm_exe = os.path.join(root, f)
                    return

        # Download
        zip_path = os.path.join(lhm_dir, "lhm_download.zip")
        logger.info("LHM: downloading portable (8.5MB)...")

        try:
            req = urllib.request.Request(
                LHM_DOWNLOAD_URL,
                headers={'User-Agent': 'BangtrixToolkit/1.0'}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(zip_path, 'wb') as f:
                    f.write(resp.read())

            if os.path.getsize(zip_path) < 500000:
                logger.error("LHM: download failed (too small)")
                os.remove(zip_path)
                return

            logger.info("LHM: extracting...")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(lhm_dir)
            os.remove(zip_path)

            # Find exe location after extract
            for root, dirs, files in os.walk(lhm_dir):
                for f in files:
                    if f.lower() == "librehardwaremonitor.exe":
                        self._lhm_exe = os.path.join(root, f)
                        logger.info(f"LHM: downloaded to {self._lhm_exe}")
                        return

        except Exception as e:
            logger.warning(f"LHM download error: {e}")
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def _auto_launch_lhm(self) -> bool:
        """
        Auto-launch LHM as Administrator via PowerShell Start-Process -Verb RunAs.
        This will trigger a UAC prompt for the user to approve.
        """
        if not self._lhm_exe:
            return False

        logger.info("LHM: attempting auto-launch as Administrator...")

        try:
            # CMD-based approach: create a temporary VBS script to run as admin silently
            vbs_script = (
                "Set UAC = CreateObject(\"Shell.Application\")\n"
                f"UAC.ShellExecute \"{self._lhm_exe}\", \"--wmi\", \"{os.path.dirname(self._lhm_exe)}\", \"runas\", 0\n"
            )
            vbs_path = os.path.join(os.path.dirname(self._lhm_exe), "_lhm_launch.vbs")
            with open(vbs_path, 'w') as f:
                f.write(vbs_script)

            # Run the VBS script (no window)
            subprocess.run(
                ["wscript.exe", vbs_path],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Clean up VBS after launch
            try:
                os.remove(vbs_path)
            except:
                pass

            logger.info("LHM: auto-launch command sent (UAC may prompt)")
            return True

        except Exception as e:
            logger.warning(f"LHM auto-launch error: {e}")
            return False

    def close(self):
        """Cleanup: kill LHM if we auto-launched it"""
        if self._auto_launched:
            try:
                subprocess.run(
                    ["taskkill", "/f", "/im", "LibreHardwareMonitor.exe"],
                    capture_output=True, timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                logger.info("LHM: stopped auto-launched instance")
            except:
                pass

    def get_stats(self, gpu_id: int = 0) -> AMDGPUStats:
        """Get GPU stats from LHM/OHM via WMI"""
        name = self.gpu_names[gpu_id] if gpu_id < len(self.gpu_names) else f"AMD GPU {gpu_id}"
        stats = AMDGPUStats(gpu_id=gpu_id, gpu_name=name, is_available=True)

        # Only works if LHM is running
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "$sensors = Get-WmiObject -Namespace 'root/LibreHardwareMonitor' -Class Sensor "
                "2>$null; if (-not $sensors) { $sensors = Get-WmiObject -Namespace "
                "'root/OpenHardwareMonitor' -Class Sensor 2>$null }; "
                "$sensors | Where-Object { $_.Value -gt 0 } | "
                "Select-Object SensorType, Name, Value | ConvertTo-Json"
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    stype = item.get('SensorType', '')
                    sname = item.get('Name', '')
                    svalue = float(item.get('Value', 0))
                    if stype == 'Temperature' and 'GPU' in sname:
                        stats.temperature = svalue
                    elif stype == 'Fan' and 'GPU' in sname:
                        stats.fan_speed = int(svalue)
                    elif stype == 'Load' and 'GPU' in sname:
                        if 'Memory' not in sname:
                            stats.utilization_gpu = svalue
                        else:
                            stats.utilization_memory = svalue
                    elif stype == 'Clock' and 'GPU' in sname:
                        if 'Memory' in sname:
                            stats.memory_clock = int(svalue)
                        elif 'Core' in sname:
                            stats.core_clock = int(svalue)
        except Exception as e:
            logger.warning(f"LHM sensor error: {e}")

        return stats