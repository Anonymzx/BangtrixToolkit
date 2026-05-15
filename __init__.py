"""
BANGTRIXTOOLKIT - ComfyUI Custom Nodes
======================================
Translate Universal + AMD Monitor Overlay
"""

import importlib

# Dynamic import — hanya load node yang benar-benar ada
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

try:
    _mod = importlib.import_module(".nodes.translate_universal", package=__package__)
    if hasattr(_mod, "NODE_CLASS_MAPPINGS"):
        NODE_CLASS_MAPPINGS.update(_mod.NODE_CLASS_MAPPINGS)
    if hasattr(_mod, "NODE_DISPLAY_NAME_MAPPINGS"):
        NODE_DISPLAY_NAME_MAPPINGS.update(_mod.NODE_DISPLAY_NAME_MAPPINGS)
    print("✅ BANGTRIXTOOLKIT: Loaded translate_universal")
except Exception as e:
    print(f"⚠️ BANGTRIXTOOLKIT: Skipped translate_universal: {e}")

WEB_DIRECTORY = "web"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY"
]


# ============================================================
# 🚀 SERVER EXTENSION — AMD Monitor Overlay (WebSocket)
# ============================================================

async def on_app_started(app):
    """Register WebSocket endpoint for AMD Monitor overlay"""
    import asyncio
    from aiohttp import web
    from .server.amd_server import get_amd_server

    amd_server = get_amd_server()

    async def websocket_handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await amd_server.handle_client(ws)
        return ws

    try:
        app.router.add_get('/ws/amd_monitor', websocket_handler)
        print("🔴 BANGTRIXTOOLKIT: AMD Monitor WebSocket at /ws/amd_monitor")
    except RuntimeError:
        pass  # Route already registered

    if not amd_server.running:
        amd_server.start_streaming(asyncio.get_event_loop())
        print("✅ BANGTRIXTOOLKIT: AMD Monitor overlay streaming started")


# Register with ComfyUI
try:
    from server import PromptServer
    prompt_server = PromptServer.instance
    prompt_server.app.on_startup.append(on_app_started)
    print("✅ BANGTRIXTOOLKIT: Server extension registered (AMD Monitor overlay)")
except Exception as e:
    print(f"⚠️ BANGTRIXTOOLKIT: Server extension skipped: {e}")