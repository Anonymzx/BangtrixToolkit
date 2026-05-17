"""
Universal Hardware Monitor Server
==================================
WebSocket server for streaming GPU/Hardware stats to frontend.
"""

import asyncio
import json
import logging
from collections import deque
from typing import Set, Dict

logger = logging.getLogger(__name__)


class HardwareMonitorServer:
    def __init__(self):
        self.monitor = None
        self.clients: Set = set()
        self.running = False
        self.update_interval = 0.5
        self._stream_task = None
        self._process_monitor = None
        self.history_maxlen = 60
        self.gpu_history: Dict[int, deque] = {}

    def _get_monitor(self):
        if self.monitor is None:
            from . import get_universal_monitor
            self.monitor = get_universal_monitor()
        return self.monitor

    def _get_process_monitor(self):
        if self._process_monitor is None:
            try:
                from .process_monitor import get_process_monitor
                self._process_monitor = get_process_monitor()
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
                    self.clients.discard(client_list[i])

    async def handle_client(self, ws):
        self.clients.add(ws)
        # Auto-start streaming when first client connects
        self.start_streaming()
        logger.info(f"HW Monitor: Client connected. Total clients: {len(self.clients)}")
        
        # Send initial stats immediately
        try:
            monitor = self._get_monitor()
            data = self._build_stats_data(monitor)
            await ws.send_str(json.dumps(data))
        except Exception:
            pass
        
        try:
            async for msg in ws:
                if msg.type == 1:
                    await self._handle_message(ws, msg.data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"HW Monitor: Client error: {e}")
        finally:
            self.clients.discard(ws)

    async def _handle_message(self, ws, raw: str):
        try:
            cmd = json.loads(raw)
            cmd_type = cmd.get("type", "")
            if cmd_type == "ping":
                await ws.send_str(json.dumps({"type": "pong"}))
            elif cmd_type == "request_stats":
                monitor = self._get_monitor()
                data = self._build_stats_data(monitor)
                await ws.send_str(json.dumps(data))
        except json.JSONDecodeError:
            if raw == "ping":
                await ws.send_str("pong")

    def _build_stats_data(self, monitor, gpu_id: int = 0):
        if not monitor.available:
            return {"type": "hw_stats", "gpu_id": gpu_id, "gpu_name": "", "gpu_count": monitor.gpu_count,
                    "vendor": monitor.vendor, "os_type": monitor.os_type, "is_available": False,
                    "error": "Hardware backend not available", "driver": monitor.driver, "history": []}
        stats = monitor.get_gpu_stats(gpu_id)
        if gpu_id not in self.gpu_history:
            self.gpu_history[gpu_id] = deque(maxlen=self.history_maxlen)
        self.gpu_history[gpu_id].append(stats.utilization_gpu)
        return {
            "type": "hw_stats",
            "gpu_id": stats.gpu_id,
            "gpu_name": stats.gpu_name or f"GPU {stats.gpu_id}",
            "gpu_count": monitor.gpu_count,
            "vendor": stats.vendor or monitor.vendor,
            "os_type": monitor.os_type,
            "driver": stats.driver or monitor.driver or "unknown",
            "is_apu": stats.is_apu,
            "is_available": stats.is_available,
            "gpu_utilization": round(stats.utilization_gpu, 1),
            "vram_usage_pct": round(stats.safe_memory_pct(), 1),
            "vram_used_mb": round(stats.memory_used / (1024 * 1024), 0) if stats.memory_used > 0 else 0,
            "vram_total_mb": round(stats.memory_total / (1024 * 1024), 0) if stats.memory_total > 0 else 0,
            "vram_shared_mb": round(stats.memory_shared / (1024 * 1024), 0) if stats.memory_shared > 0 else 0,
            "temperature": round(stats.temperature, 1) if stats.temperature > 0 else 0,
            "fan_speed": stats.fan_speed if stats.fan_speed > 0 else 0,
            "core_clock_mhz": stats.core_clock or 0,
            "power_draw_watts": round(stats.power_draw, 1) if stats.power_draw > 0 else 0,
            "history": list(self.gpu_history.get(gpu_id, [])),
        }

    async def stream_data(self):
        monitor = self._get_monitor()
        logger.info(f"HW Monitor: Stream started (interval={self.update_interval}s)")
        try:
            while self.running:
                try:
                    if monitor.available and monitor.gpu_count > 0:
                        for gpu_id in range(monitor.gpu_count):
                            await self.broadcast(json.dumps(self._build_stats_data(monitor, gpu_id)))
                    else:
                        await self.broadcast(json.dumps({"type": "hw_stats", "gpu_id": 0,
                            "is_available": False, "error": "No GPU detected", "history": []}))
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"HW Monitor: Stream error: {e}")
                await asyncio.sleep(self.update_interval)
        finally:
            logger.info("HW Monitor: Stream ended")

    def start_streaming(self):
        if self.running:
            return self._stream_task
        self.running = True
        self._stream_task = asyncio.ensure_future(self.stream_data())
        return self._stream_task

    def stop_streaming(self):
        self.running = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            self._stream_task = None


_hw_server = None
def get_hw_server() -> HardwareMonitorServer:
    global _hw_server
    if _hw_server is None:
        _hw_server = HardwareMonitorServer()
    return _hw_server