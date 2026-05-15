"""
AMD Process Monitor
===================
Monitors ComfyUI Python process memory/GPU usage during generations.
Auto-detects when generation starts/ends and records peak metrics.
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class GenerationRecord:
    """Stats for a single generation run"""
    timestamp: float
    duration: float          # seconds
    vram_peak_mb: float = 0
    vram_start_mb: float = 0
    vram_end_mb: float = 0
    vram_delta_mb: float = 0   # peak - start
    ram_peak_mb: float = 0
    ram_start_mb: float = 0
    ram_end_mb: float = 0
    cpu_peak: float = 0        # CPU utilization peak during generation
    error: Optional[str] = None


@dataclass
class ProcessSnapshot:
    """Snapshot of a process at a point in time"""
    timestamp: float
    memory_rss_mb: float
    memory_vms_mb: float
    cpu_percent: float
    num_threads: int


class ComfyProcessMonitor:
    """Monitors the ComfyUI main process for generation metrics"""

    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self._process = None
        self._process_pid = None
        self._running = False
        self._thread = None

        # Generation detection
        self._is_generating = False
        self._gen_start_time = 0
        self._current_record = None
        self._prev_memory_mb = 0

        # History
        self.history: List[GenerationRecord] = []
        self.current: Optional[GenerationRecord] = None

        # Snapshots during current generation (for graph)
        self._snapshots: List[ProcessSnapshot] = []

        # Mutex for thread safety
        self._lock = threading.Lock()

        # Threshold tuning — lebih sensitif
        self._MEMORY_START_THRESHOLD_MB = 50   # sebelumnya 100
        self._CPU_START_THRESHOLD = 15          # sebelumnya 20
        self._MEMORY_END_THRESHOLD_MB = -30     # sebelumnya -50
        self._CPU_END_THRESHOLD = 8             # sebelumnya 10

    def find_comfy_process(self) -> bool:
        """Find the ComfyUI main process"""
        try:
            import psutil
            current_pid = None

            # Method 1: Current process could be the ComfyUI worker
            proc = psutil.Process()
            proc_name = proc.name().lower()

            # Check if we're running inside ComfyUI
            cmdline = proc.cmdline()
            cmdline_str = ' '.join(cmdline).lower()
            if 'comfyui' in cmdline_str or 'main.py' in cmdline_str or 'comfy' in cmdline_str:
                current_pid = proc.pid

            # Method 2: Find by name
            if not current_pid:
                for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        name = (p.info['name'] or '').lower()
                        cl = ' '.join(p.info['cmdline'] or []).lower()
                        if ('python' in name or 'python' in cl) and ('comfy' in cl or 'main.py' in cl):
                            current_pid = p.info['pid']
                            break
                        # Also catch 'nodes' or 'comfy' in path
                        if ('python' in name) and ('comfy' in cl):
                            current_pid = p.info['pid']
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            if current_pid:
                self._process_pid = current_pid
                self._process = psutil.Process(current_pid)
                logger.info(f"Process Monitor: Found ComfyUI PID={current_pid}")
                return True

            logger.warning("Process Monitor: Could not find ComfyUI process")
            return False

        except ImportError:
            logger.warning("Process Monitor: psutil not installed")
            return False
        except Exception as e:
            logger.warning(f"Process Monitor: Find error: {e}")
            return False

    def start_monitoring(self):
        """Start background polling thread"""
        if self._running:
            return
        if not self.find_comfy_process():
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Process Monitor: Started monitoring")

    def stop_monitoring(self):
        """Stop background polling"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _poll_loop(self):
        """Main polling loop"""
        try:
            import psutil
        except ImportError:
            self._running = False
            return

        while self._running:
            try:
                if not self._process or not self._process.is_running():
                    logger.warning("Process Monitor: Process died, restarting...")
                    if not self.find_comfy_process():
                        time.sleep(self.poll_interval * 10)
                        continue

                # Get memory info
                mem_info = self._process.memory_info()
                cpu_percent = self._process.cpu_percent(interval=0)
                rss_mb = mem_info.rss / (1024 * 1024)
                vms_mb = mem_info.vms / (1024 * 1024)
                num_threads = self._process.num_threads()

                snapshot = ProcessSnapshot(
                    timestamp=time.time(),
                    memory_rss_mb=rss_mb,
                    memory_vms_mb=vms_mb,
                    cpu_percent=cpu_percent,
                    num_threads=num_threads,
                )

                # Detect generation: significant & sustained memory increase
                mem_delta = rss_mb - self._prev_memory_mb

                with self._lock:
                    if not self._is_generating:
                        # Start condition: tuned thresholds
                        if mem_delta > self._MEMORY_START_THRESHOLD_MB or cpu_percent > self._CPU_START_THRESHOLD:
                            self._is_generating = True
                            self._gen_start_time = time.time()
                            self._current_record = GenerationRecord(
                                timestamp=self._gen_start_time,
                                duration=0,
                                vram_start_mb=rss_mb,
                                vram_peak_mb=rss_mb,
                                ram_start_mb=rss_mb,
                                ram_peak_mb=rss_mb,
                            )
                            self._snapshots = [snapshot]
                            logger.info(
                                f"Process Monitor: Generation START "
                                f"(RAM: {rss_mb:.0f}MB, CPU: {cpu_percent:.1f}%)"
                            )
                    else:
                        # In middle of generation — track peak
                        if self._current_record:
                            self._current_record.vram_peak_mb = max(
                                self._current_record.vram_peak_mb, rss_mb
                            )
                            self._current_record.ram_peak_mb = max(
                                self._current_record.ram_peak_mb, rss_mb
                            )
                            self._current_record.cpu_peak = max(
                                self._current_record.cpu_peak, cpu_percent
                            )
                        self._snapshots.append(snapshot)

                        # End condition: tuned thresholds
                        if mem_delta < self._MEMORY_END_THRESHOLD_MB and cpu_percent < self._CPU_END_THRESHOLD:
                            self._finalize_generation(rss_mb)
                            logger.info(
                                f"Process Monitor: Generation END "
                                f"(duration={self.current.duration:.1f}s, "
                                f"peak RAM={self.current.ram_peak_mb:.0f}MB)"
                            )

                self._prev_memory_mb = rss_mb

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.warning("Process Monitor: Process access error")
                time.sleep(self.poll_interval * 5)
            except Exception as e:
                logger.debug(f"Process Monitor: Poll error: {e}")

            time.sleep(self.poll_interval)

    def _finalize_generation(self, end_memory_mb: float):
        """Complete a generation record"""
        if not self._current_record:
            return

        self._current_record.duration = time.time() - self._gen_start_time
        self._current_record.vram_end_mb = end_memory_mb
        self._current_record.ram_end_mb = end_memory_mb
        self._current_record.vram_delta_mb = (
            self._current_record.vram_peak_mb - self._current_record.vram_start_mb
        )

        self.current = self._current_record
        self.history.append(self._current_record)

        # Keep last 50 records
        if len(self.history) > 50:
            self.history = self.history[-50:]

        # Reset
        self._is_generating = False
        self._current_record = None
        self._snapshots = []

    def get_current_generation(self) -> GenerationRecord:
        """Get current in-progress generation record"""
        with self._lock:
            if self._is_generating and self._current_record:
                return self._current_record
        return GenerationRecord(timestamp=0, duration=0)

    def get_last_generation(self) -> Optional[GenerationRecord]:
        """Get the most recent finished generation"""
        if self.history:
            return self.history[-1]
        return None

    def get_summary(self) -> str:
        """Get a text summary of all generations"""
        if not self.history:
            return "No generations recorded yet."

        lines = [f"=== ComfyUI Process Monitor ==="]
        total_time = 0
        peak_vram = 0
        peak_ram = 0

        for i, gen in enumerate(self.history[-5:]):  # Last 5
            total_time += gen.duration
            peak_vram = max(peak_vram, gen.vram_peak_mb)
            peak_ram = max(peak_ram, gen.ram_peak_mb)

            lines.append(
                f"  #{i + 1}: {gen.duration:.1f}s "
                f"| RAM: {gen.ram_start_mb:.0f}→{gen.ram_peak_mb:.0f}→{gen.ram_end_mb:.0f}MB"
            )
            if gen.vram_delta_mb > 0:
                lines[-1] += f" (+{gen.vram_delta_mb:.0f}MB peak)"

        lines.append(
            f"  --- Total: {total_time:.1f}s | "
            f"Peak RAM: {peak_ram:.0f}MB | "
            f"Peak VRAM: {peak_vram:.0f}MB"
        )

        return "\n".join(lines)

    @property
    def is_generating(self) -> bool:
        return self._is_generating


# Singleton
_process_monitor = None


def get_process_monitor() -> ComfyProcessMonitor:
    global _process_monitor
    if _process_monitor is None:
        _process_monitor = ComfyProcessMonitor()
    return _process_monitor


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mon = get_process_monitor()
    mon.start_monitoring()

    print("Monitoring ComfyUI process...")
    print("Run a generation in ComfyUI to see stats.")
    print("Press Ctrl+C to stop and see summary.\n")

    try:
        while True:
            time.sleep(5)
            if mon.is_generating:
                gen = mon.get_current_generation()
                print(f"  ⚡ Generating... {gen.duration:.1f}s | "
                      f"Peak: {gen.vram_peak_mb:.0f}MB")
            else:
                last = mon.get_last_generation()
                if last:
                    print(f"  Last gen: {last.duration:.1f}s | "
                          f"Peak: {last.vram_peak_mb:.0f}MB | "
                          f"Delta: {last.vram_delta_mb:.0f}MB")
    except KeyboardInterrupt:
        pass
    finally:
        mon.stop_monitoring()
        print("\n" + mon.get_summary())