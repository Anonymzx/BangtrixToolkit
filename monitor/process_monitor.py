"""
ComfyUI Process Monitor
=======================
Monitors ComfyUI process during image generation.
Auto-detects generation start/end and records peak memory/CPU.

Usage:
    from monitor import get_process_monitor
    monitor = get_process_monitor()
    monitor.start_monitoring()
    # ... generate images ...
    print(monitor.get_summary())
"""

import logging
import time
import threading
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class GenerationRecord:
    """Stats for a single generation run"""
    timestamp: float = 0.0
    duration: float = 0.0
    vram_peak_mb: float = 0.0
    vram_start_mb: float = 0.0
    vram_end_mb: float = 0.0
    vram_delta_mb: float = 0.0
    ram_peak_mb: float = 0.0
    ram_start_mb: float = 0.0
    ram_end_mb: float = 0.0
    cpu_peak: float = 0.0
    error: Optional[str] = None


@dataclass
class ProcessSnapshot:
    """Point-in-time process metrics"""
    timestamp: float
    memory_rss_mb: float
    memory_vms_mb: float
    cpu_percent: float
    num_threads: int


class ComfyProcessMonitor:
    """Monitors ComfyUI process for generation metrics"""

    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self._process = None
        self._process_pid = None
        self._running = False
        self._thread = None
        self._is_generating = False
        self._gen_start_time = 0.0
        self._current_record: Optional[GenerationRecord] = None
        self._prev_memory_mb = 0.0
        self.history: List[GenerationRecord] = []
        self.current: Optional[GenerationRecord] = None
        self._snapshots: List[ProcessSnapshot] = []
        self._lock = threading.Lock()

        # Detection thresholds (tuned)
        self._MEMORY_START_THRESHOLD_MB = 50
        self._CPU_START_THRESHOLD = 15
        self._MEMORY_END_THRESHOLD_MB = -30
        self._CPU_END_THRESHOLD = 8

    def find_comfy_process(self) -> bool:
        """Auto-detect ComfyUI Python process"""
        try:
            import psutil
            pid = None
            current = psutil.Process()
            cmdline = ' '.join(current.cmdline()).lower()

            # Check if WE are the ComfyUI process
            if 'comfy' in cmdline or 'main.py' in cmdline:
                pid = current.pid

            # Search by name
            if not pid:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        name = (proc.info['name'] or '').lower()
                        cl = ' '.join(proc.info['cmdline'] or []).lower()
                        if ('python' in name or 'python' in cl) and ('comfy' in cl or 'main.py' in cl):
                            pid = proc.info['pid']
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            if pid:
                self._process_pid = pid
                self._process = psutil.Process(pid)
                logger.info(f"Process Monitor: found PID {pid}")
                return True

            logger.warning("Process Monitor: ComfyUI not found")
            return False
        except Exception as e:
            logger.warning(f"Process Monitor: find error: {e}")
            return False

    def start_monitoring(self):
        """Begin background monitoring thread"""
        if self._running:
            return
        if not self.find_comfy_process():
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Process Monitor: started")

    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _poll_loop(self):
        try:
            import psutil
        except ImportError:
            self._running = False
            return

        while self._running:
            try:
                if not self._process or not self._process.is_running():
                    if not self.find_comfy_process():
                        time.sleep(self.poll_interval * 10)
                        continue

                mem = self._process.memory_info()
                cpu = self._process.cpu_percent(interval=0)
                rss_mb = mem.rss / (1024 * 1024)
                delta = rss_mb - self._prev_memory_mb
                snap = ProcessSnapshot(time.time(), rss_mb, mem.vms / (1024*1024), cpu, self._process.num_threads())

                with self._lock:
                    if not self._is_generating:
                        if delta > self._MEMORY_START_THRESHOLD_MB or cpu > self._CPU_START_THRESHOLD:
                            self._is_generating = True
                            self._gen_start_time = time.time()
                            self._current_record = GenerationRecord(
                                timestamp=self._gen_start_time, duration=0,
                                vram_start_mb=rss_mb, vram_peak_mb=rss_mb,
                                ram_start_mb=rss_mb, ram_peak_mb=rss_mb,
                            )
                            self._snapshots = [snap]
                            logger.info(f"Process Monitor: START (RAM: {rss_mb:.0f}MB)")
                    else:
                        if self._current_record:
                            self._current_record.vram_peak_mb = max(self._current_record.vram_peak_mb, rss_mb)
                            self._current_record.ram_peak_mb = max(self._current_record.ram_peak_mb, rss_mb)
                            self._current_record.cpu_peak = max(self._current_record.cpu_peak, cpu)
                        self._snapshots.append(snap)

                        if delta < self._MEMORY_END_THRESHOLD_MB and cpu < self._CPU_END_THRESHOLD:
                            self._finalize(rss_mb)
                            logger.info(f"Process Monitor: END ({self.current.duration:.1f}s)")

                self._prev_memory_mb = rss_mb
            except Exception as e:
                logger.debug(f"Process Monitor: {e}")
            time.sleep(self.poll_interval)

    def _finalize(self, end_mb: float):
        if not self._current_record:
            return
        self._current_record.duration = time.time() - self._gen_start_time
        self._current_record.vram_end_mb = end_mb
        self._current_record.ram_end_mb = end_mb
        self._current_record.vram_delta_mb = self._current_record.vram_peak_mb - self._current_record.vram_start_mb
        self.current = self._current_record
        self.history.append(self._current_record)
        if len(self.history) > 50:
            self.history = self.history[-50:]
        self._is_generating = False
        self._current_record = None
        self._snapshots = []

    @property
    def is_generating(self) -> bool:
        return self._is_generating

    def get_current_generation(self) -> GenerationRecord:
        with self._lock:
            if self._is_generating and self._current_record:
                return self._current_record
        return GenerationRecord()

    def get_last_generation(self) -> Optional[GenerationRecord]:
        if self.history:
            return self.history[-1]
        return None

    def get_summary(self) -> str:
        if not self.history:
            return "No generations recorded."
        lines = ["=== ComfyUI Process Monitor ==="]
        total_time = peak_ram = 0
        for gen in self.history[-5:]:
            total_time += gen.duration
            peak_ram = max(peak_ram, gen.ram_peak_mb)
            lines.append(f"  #{len(lines)}: {gen.duration:.1f}s | RAM: {gen.ram_start_mb:.0f}→{gen.ram_peak_mb:.0f}MB")
        lines.append(f"  --- Total: {total_time:.1f}s | Peak RAM: {peak_ram:.0f}MB")
        return "\n".join(lines)


# Singleton
_process_monitor = None


def get_process_monitor() -> ComfyProcessMonitor:
    global _process_monitor
    if _process_monitor is None:
        _process_monitor = ComfyProcessMonitor()
    return _process_monitor