"""
AMD Monitor Server
==================
WebSocket server for streaming AMD GPU stats to frontend.
Supports multi-GPU, commands, history, and ComfyUI process monitoring.
Default interval: 5s
"""

import asyncio
import json
import logging
from collections import deque
from typing import Set, Dict

logger = logging.getLogger(__name__)


class AMDMonitorServer:
    def __init__(self):
        self.monitor = None  # Lazy load
        self.clients: Set = set()
        self.running = False
        self.update_interval = 0.5  # seconds — real-time 500ms
        self._stream_task = None

        # Process monitor
        self._process_monitor = None

        # Multi-GPU history — 60 points for 30s at 0.5s interval = smooth real-time sparkline
        self.history_maxlen = 60
        self.gpu_history: Dict[int, deque] = {}

    def _get_monitor(self):
        if self.monitor is None:
            try:
                from ..monitor import get_amd_monitor
                self.monitor = get_amd_monitor()
            except ImportError:
                from ..utils.amd_utils import get_amd_monitor as _legacy_monitor
                self.monitor = _legacy_monitor()
        return self.monitor

    def _get_process_monitor(self):
        if self._process_monitor is None:
            try:
                from ..monitor.process_monitor import get_process_monitor
                self._process_monitor = get_process_monitor()
                self._process_monitor.start_monitoring()
            except ImportError:
                from ..utils.amd_process_monitor import get_process_monitor as _legacy_pm
                self._process_monitor = _legacy_pm()
                self._process_monitor.start_monitoring()
            except Exception as e:
                logger.debug(f"Process monitor init: {e}")
        return self._process_monitor

    async def broadcast(self, message: str):
        if not self.clients:
            return
        results = await asyncio.gather(
            *[client.send_str(message) for client in self.clients.copy()],
            return_exceptions=True
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                client_list = list(self.clients)
                if i < len(client_list):
                    logger.debug(f"AMD Monitor: Removing dead client: {result}")
                    self.clients.discard(client_list[i])

    async def handle_client(self, ws):
        self.clients.add(ws)
        logger.info(f"AMD Monitor: Client connected. Total clients: {len(self.clients)}")

        try:
            async for msg in ws:
                if msg.type == 1:
                    await self._handle_message(ws, msg.data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"AMD Monitor: Client error: {e}")
        finally:
            self.clients.discard(ws)
            logger.info(f"AMD Monitor: Client disconnected. Total clients: {len(self.clients)}")

    async def _handle_message(self, ws, raw: str):
        try:
            cmd = json.loads(raw)
            cmd_type = cmd.get("type", "")

            if cmd_type == "ping":
                await ws.send_str(json.dumps({"type": "pong"}))

            elif cmd_type == "set_interval":
                interval = float(cmd.get("interval", 5.0))
                self.update_interval = max(0.5, min(30.0, interval))
                await ws.send_str(json.dumps({
                    "type": "config_updated",
                    "update_interval": self.update_interval
                }))

            elif cmd_type == "get_history":
                gpu_id = cmd.get("gpu_id", 0)
                history = list(self.gpu_history.get(gpu_id, []))
                await ws.send_str(json.dumps({
                    "type": "history",
                    "gpu_id": gpu_id,
                    "values": history
                }))

            elif cmd_type == "request_stats":
                monitor = self._get_monitor()
                data = self._build_stats_data(monitor)
                process = self._get_process_monitor()
                if process:
                    data["process"] = self._build_process_data(process)
                await ws.send_str(json.dumps(data))

            else:
                await ws.send_str(json.dumps({
                    "type": "error",
                    "message": f"Unknown command: {cmd_type}"
                }))

        except json.JSONDecodeError:
            if raw == "ping":
                await ws.send_str("pong")

    def _build_process_data(self, process):
        """Build process monitoring payload"""
        data = {
            "is_generating": process.is_generating,
        }

        if process.is_generating:
            gen = process.get_current_generation()
            data["generation"] = {
                "duration": round(gen.duration, 1),
                "vram_peak_mb": round(gen.vram_peak_mb, 0),
                "ram_start_mb": round(gen.ram_start_mb, 0),
                "ram_peak_mb": round(gen.ram_peak_mb, 0),
                "cpu_peak": round(gen.cpu_peak, 1),
            }
        else:
            last = process.get_last_generation()
            if last:
                data["last_generation"] = {
                    "duration": round(last.duration, 1),
                    "vram_peak_mb": round(last.vram_peak_mb, 0),
                    "vram_delta_mb": round(last.vram_delta_mb, 0),
                    "ram_start_mb": round(last.ram_start_mb, 0),
                    "ram_peak_mb": round(last.ram_peak_mb, 0),
                    "ram_end_mb": round(last.ram_end_mb, 0),
                    "cpu_peak": round(last.cpu_peak, 1),
                }

        # Generation count
        data["generation_count"] = len(process.history) if process.history else 0

        return data

    def _build_stats_data(self, monitor, gpu_id: int = 0):
        if not monitor.available:
            return {
                "type": "amd_stats",
                "gpu_id": gpu_id,
                "gpu_name": "",
                "gpu_count": monitor.gpu_count,
                "is_available": False,
                "error": "AMD backend not available",
                "method": monitor.method,
                "history": []
            }

        stats = monitor.get_gpu_stats(gpu_id)

        # Update history
        if gpu_id not in self.gpu_history:
            self.gpu_history[gpu_id] = deque(maxlen=self.history_maxlen)
        self.gpu_history[gpu_id].append(stats.utilization_gpu)

        data = {
            "type": "amd_stats",
            "gpu_id": stats.gpu_id,
            "gpu_name": stats.gpu_name or f"AMD GPU {stats.gpu_id}",
            "gpu_count": monitor.gpu_count,
            "method": monitor.method or "unknown",
            "is_available": stats.is_available,
            "gpu_utilization": round(stats.utilization_gpu, 1),
            "vram_usage_pct": round(stats.utilization_memory, 1) if isinstance(stats.utilization_memory, (int, float)) and stats.utilization_memory == stats.utilization_memory else 0,
            "vram_used_mb": round(stats.memory_used / (1024 * 1024), 0) if stats.memory_used > 0 else 0,
            "vram_total_mb": round(stats.memory_total / (1024 * 1024), 0) if stats.memory_total > 0 else 0,
            "temperature": round(stats.temperature, 1) if stats.temperature > 0 else 0,
            "fan_speed": stats.fan_speed if stats.fan_speed > 0 else 0,
            "core_clock_mhz": stats.core_clock if stats.core_clock > 0 else 0,
            "memory_clock_mhz": stats.memory_clock if stats.memory_clock > 0 else 0,
            "power_draw_watts": round(stats.power_draw, 1) if stats.power_draw > 0 else 0,
            "history": list(self.gpu_history.get(gpu_id, [])),
        }

        if not stats.is_available and stats.error_message:
            data["error"] = stats.error_message

        return data

    async def stream_data(self):
        monitor = self._get_monitor()
        process_mon = self._get_process_monitor()
        logger.info(f"AMD Monitor: Stream data loop started (interval={self.update_interval}s)")

        try:
            while self.running:
                try:
                    if monitor.available and monitor.gpu_count > 0:
                        for gpu_id in range(monitor.gpu_count):
                            data = self._build_stats_data(monitor, gpu_id)

                            # Attach process monitoring data
                            if process_mon:
                                data["process"] = self._build_process_data(process_mon)

                            await self.broadcast(json.dumps(data))
                    else:
                        data = {
                            "type": "amd_stats",
                            "gpu_id": 0,
                            "gpu_name": "",
                            "gpu_count": monitor.gpu_count,
                            "is_available": False,
                            "error": "AMD backend not available",
                            "method": monitor.method,
                            "history": []
                        }
                        await self.broadcast(json.dumps(data))

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"AMD Monitor: Stream error: {e}")

                await asyncio.sleep(self.update_interval)
        finally:
            logger.info("AMD Monitor: Stream data loop ended")

    def start_streaming(self):
        if self.running:
            return self._stream_task

        self.running = True
        logger.info("AMD Monitor: Starting data stream")

        self._stream_task = asyncio.ensure_future(self.stream_data())
        return self._stream_task

    def stop_streaming(self):
        self.running = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            self._stream_task = None
            logger.info("AMD Monitor: Stream stopped")


# Singleton instance
_amd_server = None


def get_amd_server() -> AMDMonitorServer:
    global _amd_server
    if _amd_server is None:
        _amd_server = AMDMonitorServer()
    return _amd_server