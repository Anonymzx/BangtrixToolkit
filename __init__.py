"""
BANGTRIXTOOLKIT - ComfyUI Custom Nodes
======================================
Translate Universal + Universal Hardware Monitor Overlay
"""

import importlib
import logging

logger = logging.getLogger(__name__)

# Dynamic import — hanya load node yang benar-benar ada
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

try:
    _mod = importlib.import_module(".btx_nodes.translate_universal", package=__package__)
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
# 🚀 SERVER EXTENSION — Universal Hardware Monitor WebSocket
# ============================================================
# Register WebSocket route. Uses direct file path to avoid
# Python module naming issues with ComfyUI's load mechanism.
import sys as _sys, os as _os
from importlib import util as _util

try:
    import server as _comfy_server
    _PromptServer = _comfy_server.PromptServer
    if _PromptServer.instance:
        _app = _PromptServer.instance.app
        from aiohttp import web
        # Import hw_server directly via absolute file path
        _hws_path = _os.path.join(_os.path.dirname(__file__), "monitor", "hw_server.py")
        _spec = _util.spec_from_file_location("BangtrixToolkit_hw_server", _hws_path)
        _hws_mod = _util.module_from_spec(_spec)
        _sys.modules['BangtrixToolkit_hw_server'] = _hws_mod
        _spec.loader.exec_module(_hws_mod)
        _get_hw_server = _hws_mod.get_hw_server
        
        hw_server = _get_hw_server()
        async def ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await hw_server.handle_client(ws)
            return ws
        _app.router.add_get('/ws/hw_monitor', ws_handler)
        print("🖥️ BANGTRIXTOOLKIT: HW Monitor WebSocket at /ws/hw_monitor")
    else:
        print("🖥️ BANGTRIXTOOLKIT: PromptServer pending")
except Exception as e:
    print(f"⚠️ BANGTRIXTOOLKIT: Server extension skipped: {e}")
