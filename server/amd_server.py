"""
AMD Monitor Server
==================
WebSocket server for streaming AMD GPU stats to frontend
"""

import asyncio
import json
import logging
from typing import Set

logger = logging.getLogger(__name__)


class AMDMonitorServer:
    def __init__(self):
        self.monitor = None  # Lazy load
        self.clients: Set = set()
        self.running = False
        self.update_interval = 1.0  # seconds

    def _get_monitor(self):
        """Lazy load monitor to avoid import issues at startup"""
        if self.monitor is None:
            from ..utils.amd_utils import get_amd_monitor
            self.monitor = get_amd_monitor()
        return self.monitor

    async def broadcast(self, message: str):
        """Send data to all connected clients"""
        if self.clients:
            await asyncio.gather(
                *[client.send_str(message) for client in self.clients],
                return_exceptions=True
            )

    async def handle_client(self, ws):
        """Handle WebSocket client connection"""
        self.clients.add(ws)
        logger.info(f"AMD Monitor: Client connected. Total clients: {len(self.clients)}")
        
        try:
            async for msg in ws:
                if msg.type == 1:  # Text message
                    if msg.data == "ping":
                        await ws.send_str("pong")
        except Exception as e:
            logger.error(f"AMD Monitor: Client error: {e}")
        finally:
            self.clients.discard(ws)
            logger.info(f"AMD Monitor: Client disconnected. Total clients: {len(self.clients)}")

    async def stream_data(self):
        """Stream GPU stats periodically"""
        monitor = self._get_monitor()
        
        while self.running:
            try:
                if monitor.available:
                    stats = monitor.get_gpu_stats(0)  # GPU 0
                    
                    data = {
                        "type": "amd_stats",
                        "gpu_id": stats.gpu_id,
                        "gpu_utilization": stats.utilization_gpu,
                        "vram_usage_pct": stats.utilization_memory,
                        "vram_used_mb": stats.memory_used / (1024 * 1024),
                        "vram_total_mb": stats.memory_total / (1024 * 1024),
                        "temperature": stats.temperature,
                        "fan_speed": stats.fan_speed,
                        "is_available": stats.is_available,
                        "method": monitor.method,
                        "gpu_count": monitor.gpu_count
                    }
                else:
                    data = {
                        "type": "amd_stats",
                        "is_available": False,
                        "error": "AMD backend not available",
                        "method": None,
                        "gpu_count": 0
                    }
                
                await self.broadcast(json.dumps(data))
                
            except Exception as e:
                logger.error(f"AMD Monitor: Stream error: {e}")
            
            await asyncio.sleep(self.update_interval)

    def start(self, loop=None):
        """Start the monitoring loop safely"""
        if self.running:
            return
        
        self.running = True
        logger.info("AMD Monitor: Starting data stream")


# Singleton instance
_amd_server = None

def get_amd_server() -> AMDMonitorServer:
    global _amd_server
    if _amd_server is None:
        _amd_server = AMDMonitorServer()
    return _amd_server