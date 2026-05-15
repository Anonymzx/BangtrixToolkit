"""
BANGTRIXTOOLKIT - ComfyUI Custom Nodes
======================================
AMD Monitor & Translate Universal
"""

from .nodes.translate_universal import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS
)

from .nodes.amd_monitor import (
    NODE_CLASS_MAPPINGS as AMD_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as AMD_NODE_DISPLAY_NAME_MAPPINGS
)

# Gabungkan semua node mappings
NODE_CLASS_MAPPINGS = {**NODE_CLASS_MAPPINGS, **AMD_NODE_CLASS_MAPPINGS}
NODE_DISPLAY_NAME_MAPPINGS = {**NODE_DISPLAY_NAME_MAPPINGS, **AMD_NODE_DISPLAY_NAME_MAPPINGS}

WEB_DIRECTORY = "./web"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY"
]


# ============================================================
# 🚀 SERVER EXTENSION - WebSocket untuk Real-Time Monitoring
# ============================================================

async def on_app_started(app):
    """Register WebSocket endpoint for AMD Monitor (FIXED: 1 argument only)"""
    import asyncio
    from aiohttp import web
    from .server.amd_server import get_amd_server
    
    amd_server = get_amd_server()
    
    async def websocket_handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await amd_server.handle_client(ws)
        return ws
    
    # Register route (safe: won't error if already registered)
    try:
        app.router.add_get('/ws/amd_monitor', websocket_handler)
        print("🔴 BANGTRIXTOOLKIT: AMD Monitor WebSocket at /ws/amd_monitor")
    except RuntimeError:
        pass  # Route already exists
    
    # Start monitoring in background
    if not amd_server.running:
        amd_server.running = True
        asyncio.create_task(amd_server.stream_data())
        print("✅ BANGTRIXTOOLKIT: AMD Monitor streaming started")


# Register with ComfyUI (FIXED: lambda to match signature)
try:
    from server import PromptServer
    prompt_server = PromptServer.instance
    
    # Append our async handler (ComfyUI only passes 'app')
    prompt_server.app.on_startup.append(on_app_started)
    print("✅ BANGTRIXTOOLKIT: Server extension registered")
    
except Exception as e:
    print(f"⚠️ BANGTRIXTOOLKIT: Server extension skipped: {e}")