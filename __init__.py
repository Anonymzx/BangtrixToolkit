# -*- coding: utf-8 -*-
"""
BANGTRIXTOOLKIT - ComfyUI Custom Nodes
======================================
Translate Universal + Universal Hardware Monitor Overlay

Server-extension endpoints (all under /btx/* for consistency):

  GET  /btx/hw/stats    -> JSON GPU data (polling, primary)
  WS   /btx/ws/hw_monitor -> WebSocket streaming (fallback)
  GET  /btx/hw/health   -> Liveness check
  POST /btx/free_memory -> Aggressive VRAM + RAM flush
"""

import asyncio
import gc
import importlib
import logging
import os as _os
import sys as _sys

__version__ = "1.2.1"
__author__ = "Anonymzx"

# Ensure this package is on sys.path for absolute imports to work
_pkg_dir = _os.path.dirname(_os.path.realpath(__file__))
if _pkg_dir not in _sys.path:
    _sys.path.insert(0, _pkg_dir)

logger = logging.getLogger(__name__)

# Dynamic import  - hanya load node yang benar-benar ada
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

for _modname in ("translate_universal", "bangtrix_simple_translate"):
    try:
        _mod = importlib.import_module(
            f".btx_nodes.{_modname}", package=__package__
        )
        if hasattr(_mod, "NODE_CLASS_MAPPINGS"):
            NODE_CLASS_MAPPINGS.update(_mod.NODE_CLASS_MAPPINGS)
        if hasattr(_mod, "NODE_DISPLAY_NAME_MAPPINGS"):
            NODE_DISPLAY_NAME_MAPPINGS.update(_mod.NODE_DISPLAY_NAME_MAPPINGS)
        logger.info("[BANGTRIX] Loaded %s", _modname)
    except Exception as e:
        logger.warning("[BANGTRIX] Skipped %s: %s", _modname, e)

WEB_DIRECTORY = "web"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]


# ============================================================
# SERVER EXTENSION - Universal Hardware Monitor REST API
# ============================================================
# Provides:
#   GET  /btx/hw/stats          -> JSON GPU data (polling)
#   WS   /btx/ws/hw_monitor     -> WebSocket streaming (fallback)
#   GET  /btx/hw/health         -> Liveness check
#   POST /btx/free_memory       -> Aggressive VRAM flush

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

# Minimum interval (seconds) between accepted /btx/free_memory calls.
# Prevents a malicious or buggy client from spamming gc.collect() and
# unload_all_models(), which would DoS the prompt queue.
_FREE_MEMORY_MIN_INTERVAL_S = 10.0
_free_memory_last_call = {"t": 0.0}


def _free_memory_is_rate_limited() -> bool:
    """True if a /btx/free_memory call happened recently.

    **Must be called from inside an asyncio event loop.** The current time
    comes from ``asyncio.get_running_loop().time()`` (monotonic); if there
    is no running loop the fallback ``0.0`` means ``now - last_call`` is
    always huge and the limiter will never trip. Today the only caller is
    the aiohttp handler in ``free_memory_handler`` so this is fine, but a
    regression that invokes the limiter from a worker thread, sync code, or
    outside the loop will silently bypass rate limiting.
    """
    loop = _safe_event_loop()
    now = loop.time() if loop is not None else 0.0
    if now - _free_memory_last_call["t"] < _FREE_MEMORY_MIN_INTERVAL_S:
        return True
    _free_memory_last_call["t"] = now
    return False


def _safe_event_loop():
    """Return a running event loop if one exists, else None.

    Used by the rate limiter to get monotonic time without raising.
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


try:
    import server as _comfy_server
    _ps = _comfy_server.PromptServer

    if _ps.instance:
        _app = _ps.instance.app
        from aiohttp import web
        import importlib.util as _importlib_util

        # Load hw_server module via file path so its file_path matches
        # the on-disk location regardless of __package__ quirks.
        _hws_path = _os.path.join(
            _os.path.dirname(__file__), "monitor", "hw_server.py"
        )

        # If the file is missing we MUST refuse to register handlers —
        # otherwise every request silently falls back to the placeholder.
        if not _os.path.exists(_hws_path):
            logger.error(
                "[BANGTRIX] monitor/hw_server.py not found at %s; "
                "hardware endpoints will return placeholder data",
                _hws_path,
            )
            _hw_srv = None
        else:
            _spec = _importlib_util.spec_from_file_location(
                "BangtrixToolkit_hw_server", _hws_path
            )
            _hws_mod = _importlib_util.module_from_spec(_spec)
            # Insert into sys.modules so internal imports (`from monitor...`)
            # resolve correctly, then execute the module.
            _sys.modules["BangtrixToolkit_hw_server"] = _hws_mod
            try:
                _spec.loader.exec_module(_hws_mod)
                _hw_srv = _hws_mod.get_hw_server()
            except Exception as e:
                logger.error("[BANGTRIX] hw_server import failed: %s", e)
                _hw_srv = None

        # --- REST API endpoint (primary) ---
        async def rest_stats_handler(request):
            """Serve GPU stats. Returns valid JSON; sync work runs off-loop."""
            if _hw_srv is None:
                return web.json_response(GLOBAL_HW_CACHE)
            try:
                # Off-load the cache read (which briefly holds a lock and
                # performs a dict copy) to a worker thread so we never
                # block the aiohttp event loop.
                data = await asyncio.to_thread(_hw_srv.get_stats_json)
                return web.json_response(data)
            except Exception:
                logger.exception("[BANGTRIX] rest_stats_handler error")
                return web.json_response(GLOBAL_HW_CACHE)

        # Guard against double-registration when ComfyUI reloads the
        # custom_nodes module. aiohttp raises ValueError on duplicates.
        def _add_route(method: str, path: str, handler) -> None:
            existing = {r.canonical for r in _app.router._resources}  # type: ignore[attr-defined]
            if path in existing:
                logger.debug("[BANGTRIX] Route %s %s already registered, skipping", method, path)
                return
            _app.router.add_route(method, path, handler)

        _add_route("GET", "/btx/hw/stats", rest_stats_handler)
        logger.info("[BANGTRIX] REST API at /btx/hw/stats")

        # --- WebSocket endpoint (fallback) ---
        async def ws_handler(request):
            ws = web.WebSocketResponse(heartbeat=30.0)
            await ws.prepare(request)
            try:
                while not ws.closed:
                    if _hw_srv is None:
                        try:
                            await ws.send_json(GLOBAL_HW_CACHE)
                        except Exception:
                            break
                        await asyncio.sleep(1.0)
                        continue

                    try:
                        # Off-load sync cache read so a slow backend
                        # can't stall other WS connections on the same loop.
                        data = await asyncio.to_thread(_hw_srv.get_stats_json)
                        await ws.send_json(data)
                    except asyncio.CancelledError:
                        break
                    except ConnectionResetError:
                        break
                    except Exception:
                        logger.exception("[BANGTRIX] ws_handler send error")
                        try:
                            await ws.send_json(GLOBAL_HW_CACHE)
                        except Exception:
                            break

                    # Wait either 1s or until the socket is closed by
                    # the peer. sleep() doesn't notice peer-side closes
                    # immediately, so ws.receive(timeout=...) would be
                    # needed for true liveness — the heartbeat above is
                    # enough to detect dead TCP in practice.
                    try:
                        await asyncio.sleep(1.0)
                    except asyncio.CancelledError:
                        break
            finally:
                if not ws.closed:
                    try:
                        await ws.close()
                    except Exception:
                        pass

            return ws

        _add_route("GET", "/btx/ws/hw_monitor", ws_handler)
        logger.info("[BANGTRIX] WS at /btx/ws/hw_monitor")

        # --- Quick health check ---
        async def health_handler(request):
            return web.json_response({"status": "ok"})

        _add_route("GET", "/btx/hw/health", health_handler)
        logger.info("[BANGTRIX] Server extension registered")

        # --- Free Memory endpoint (VRAM & RAM flush) ---
        async def free_memory_handler(request):
            """Aggressive memory flush.

            Guarded against:
              1. **Rate limiting** — at most one call per
                 _FREE_MEMORY_MIN_INTERVAL_S seconds. Otherwise a
                 misbehaving client (or buggy frontend) could pin the
                 event loop with gc.collect() calls.
              2. **Origin / CSRF** — accepts only same-origin POSTs.
                 ComfyUI's own /free endpoint has the same posture.
            """
            # CSRF / Origin check (same-origin or no Origin header).
            # We accept requests that either have no Origin (e.g. curl,
            # server-to-server) or whose Origin matches the Host header.
            # ComfyUI's own /free endpoint has the same posture.
            origin = request.headers.get("Origin", "")
            host = request.headers.get("Host", "")
            if origin and host:
                origin_netloc = origin.split("//", 1)[-1].rstrip("/")
                host_netloc = host.strip()
                if origin_netloc != host_netloc:
                    return web.json_response(
                        {"status": "error", "message": "Cross-origin request rejected"},
                        status=403,
                    )

            if _free_memory_is_rate_limited():
                return web.json_response(
                    {"status": "error", "message": "Rate limited; try again later"},
                    status=429,
                )

            def _flush():
                # Run heavy sync work off the event loop.
                import comfy.model_management
                comfy.model_management.unload_all_models()
                comfy.model_management.soft_empty_cache()
                gc.collect()

            try:
                await asyncio.to_thread(_flush)
                return web.json_response(
                    {"status": "success", "message": "Memory freed"}
                )
            except Exception as e:
                logger.exception("[BANGTRIX] free_memory_handler error")
                return web.json_response(
                    {"status": "error", "message": str(e)}, status=500
                )

        _add_route("POST", "/btx/free_memory", free_memory_handler)
        logger.info("[BANGTRIX] POST /btx/free_memory registered")

    else:
        logger.warning("[BANGTRIX] PromptServer not ready; skipping extension registration")
except Exception as e:
    logger.exception("[BANGTRIX] Server extension skipped: %s", e)
