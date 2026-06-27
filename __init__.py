# -*- coding: utf-8 -*-
"""
BANGTRIXTOOLKIT - ComfyUI Custom Nodes
======================================
Translate Universal + Universal Hardware Monitor Overlay
"""

import asyncio
import gc
import importlib
import logging
import sys as _sys
import os as _os

__version__ = "1.2.0"
__author__ = "Anonymzx"

# Ensure this package is on sys.path for absolute imports to work
_pkg_dir = _os.path.dirname(_os.path.realpath(__file__))
if _pkg_dir not in _sys.path:
    _sys.path.insert(0, _pkg_dir)

logger = logging.getLogger(__name__)

# Dynamic import  - hanya load node yang benar-benar ada
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

try:
    _mod = importlib.import_module(".btx_nodes.translate_universal", package=__package__)
    if hasattr(_mod, "NODE_CLASS_MAPPINGS"):
        NODE_CLASS_MAPPINGS.update(_mod.NODE_CLASS_MAPPINGS)
    if hasattr(_mod, "NODE_DISPLAY_NAME_MAPPINGS"):
        NODE_DISPLAY_NAME_MAPPINGS.update(_mod.NODE_DISPLAY_NAME_MAPPINGS)
    print("[BANGTRIX] Loaded translate_universal")
except Exception as e:
    print(f"[BANGTRIX] Skipped translate_universal: {e}")

try:
    _mod = importlib.import_module(".btx_nodes.bangtrix_simple_translate", package=__package__)
    if hasattr(_mod, "NODE_CLASS_MAPPINGS"):
        NODE_CLASS_MAPPINGS.update(_mod.NODE_CLASS_MAPPINGS)
    if hasattr(_mod, "NODE_DISPLAY_NAME_MAPPINGS"):
        NODE_DISPLAY_NAME_MAPPINGS.update(_mod.NODE_DISPLAY_NAME_MAPPINGS)
    print("[BANGTRIX] Loaded bangtrix_simple_translate")
except Exception as e:
    print(f"[BANGTRIX] Skipped bangtrix_simple_translate: {e}")
WEB_DIRECTORY = "web"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY"
]


# ============================================================
# SERVER EXTENSION - Universal Hardware Monitor REST API
# ============================================================
# Provides:
#   GET /bangtrix/hw/stats  -> JSON GPU data (polling)
#   WS  /ws/hw_monitor      -> WebSocket streaming (fallback)

# === BULLETPROOF GLOBAL CACHE FALLBACK ===
# Declared BEFORE any route or server init. If ANYTHING goes wrong
# in the hardware server, route handlers will fall back to this.
# vram_total_mb MUST be >= 1 to prevent JS division-by-zero.
GLOBAL_HW_CACHE = {
    "type": "hw_stats",
    "gpu_id": 0,
    "gpu_name": "Starting Backend...",
    "gpu_count": 0,
    "vendor": "unknown",
    "os_type": "unknown",
    "is_available": False,
    "is_loading": True,
    "is_apu": True,
    "error": "Hardware detection in progress",
    "driver": "",
    "history": [],
    "gpu_utilization": 0.0,
    "vram_usage_pct": 0.0,
    "vram_used_mb": 0,
    "vram_total_mb": 1,          # >=1 prevents JS div/0
    "vram_shared_mb": 0,
    "temperature": 0.0,
    "fan_speed": 0,
    "core_clock_mhz": 0,
    "power_draw_watts": 0.0,
    "backend": "fallback",
}

try:
    import server as _comfy_server
    _ps = _comfy_server.PromptServer

    if _ps.instance:
        _app = _ps.instance.app
        from aiohttp import web
        import importlib.util as _importlib_util

        # Load hw_server module via file path
        _hws_path = _os.path.join(_os.path.dirname(__file__), "monitor", "hw_server.py")
        _spec = _importlib_util.spec_from_file_location("BangtrixToolkit_hw_server", _hws_path)
        _hws_mod = _importlib_util.module_from_spec(_spec)
        _sys.modules["BangtrixToolkit_hw_server"] = _hws_mod
        _spec.loader.exec_module(_hws_mod)
        _get_hw = _hws_mod.get_hw_server
        _hw_srv = _get_hw()

        # --- REST API endpoint (primary) ---
        async def rest_stats_handler(request):
            """Serve GPU stats. Always returns valid JSON - try/except is mandatory."""
            try:
                data = _hw_srv.get_stats_json()
                return web.json_response(data)
            except Exception:
                # Absolute last-resort fallback
                return web.json_response(GLOBAL_HW_CACHE)

        _app.router.add_get("/bangtrix/hw/stats", rest_stats_handler)
        print("[BANGTRIX] REST API at /bangtrix/hw/stats")

        # --- WebSocket endpoint (fallback) ---
        async def ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            _running = True
            try:
                while _running:
                    try:
                        data = _hw_srv.get_stats_json()
                        await ws.send_json(data)
                    except asyncio.CancelledError:
                        _running = False
                        break
                    except Exception:
                        try:
                            await ws.send_json(GLOBAL_HW_CACHE)
                        except Exception:
                            pass
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            return ws

        _app.router.add_get("/ws/hw_monitor", ws_handler)
        print("[BANGTRIX] WS at /ws/hw_monitor")

        # --- Quick health check ---
        async def health_handler(request):
            return web.json_response({"status": "ok"})

        _app.router.add_get("/bangtrix/hw/health", health_handler)
        print("[BANGTRIX] Server extension registered")

        # --- Free Memory endpoint (VRAM & RAM flush) ---
        async def free_memory_handler(request):
            """Aggressive memory flush: unload all models -> empty PyTorch cache -> GC collect."""
            try:
                import comfy.model_management
                comfy.model_management.unload_all_models()
                comfy.model_management.soft_empty_cache()
                gc.collect()
                return web.json_response({"status": "success", "message": "Memory freed"})
            except Exception as e:
                return web.json_response({"status": "error", "message": str(e)}, status=500)

        _app.router.add_post("/btx/free_memory", free_memory_handler)
        print("[BANGTRIX] POST /btx/free_memory registered")

    else:
        print("[BANGTRIX] PromptServer pending")
except Exception as e:
    print(f"[BANGTRIX] Server extension skipped: {e}")