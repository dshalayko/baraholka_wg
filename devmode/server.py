"""Assembles the debug app: patch fake Telegram in, then add debug routes.

The production FastAPI app is reused as-is. The only production route replaced
is GET "/", so index.html can be served with a stubbed window.Telegram.WebApp
injected — that is what lets the Mini App run in a plain browser.
"""

import json
import os
import sys
import types
from typing import Any, Dict, Optional

from devmode import env

DEVMODE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(DEVMODE_DIR, "static")
BASE_DIR = os.path.dirname(DEVMODE_DIR)

NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

TELEGRAM_SDK_TAG = '<script src="https://telegram.org/js/telegram-web-app.js"></script>'


def _patch_telegram() -> None:
    """Swap in the fake bot before any route module binds the real one.

    This has to dodge webserver/__init__.py, which runs
    `from webserver.app import app`. A plain `import webserver.telegram_client`
    therefore imports every route module first, and each of those does
    `from webserver.telegram_client import bot` — binding the real Bot into its
    own namespace before we get a chance to replace it. Registering a bare
    stand-in for the `webserver` package in sys.modules lets us import just the
    submodule we need to patch, without executing that __init__; build_app()
    restores the `app` re-export afterwards.
    """
    if "webserver" not in sys.modules:
        package = types.ModuleType("webserver")
        package.__path__ = [os.path.join(BASE_DIR, "webserver")]
        sys.modules["webserver"] = package

    from devmode import fake_telegram as fake

    import webserver.telegram_client as telegram_client

    telegram_client.bot = fake.bot
    telegram_client.upload_photo = fake.upload_photo

    # The real implementations open a Pyrogram userbot session against the real
    # channel, which is exactly what debug mode must not do.
    import comments_manager

    comments_manager.get_discussion_replies_counts = fake.get_discussion_replies_counts
    comments_manager.delete_channel_messages = fake.delete_channel_messages
    comments_manager.forward_thread_replies = fake.forward_thread_replies


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _start_param(query: Dict[str, str]) -> Optional[str]:
    explicit = query.get("startapp") or query.get("start_param")
    if explicit:
        return explicit
    if query.get("bid"):
        return f"bid_{query['bid']}"
    if query.get("bids"):
        return f"bids_{query['bids']}"
    return None


def build_app(port: int, log_level: str = "INFO"):
    base_url = env.apply(port, log_level)
    _patch_telegram()

    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse, Response

    from config import DB_PATH
    from devmode import fake_telegram as fake
    from devmode import seed as seeder
    from devmode.users import resolve_user_key, init_data_unsafe, sign_init_data, user_directory
    from webserver.app import app
    from webserver.db import ensure_db
    from webserver.settings import WEBAPP_DIR

    # Restore what the real webserver/__init__.py exports, since _patch_telegram
    # replaced the package object with a stub that never ran it.
    sys.modules["webserver"].app = app

    # Starlette resolves the first matching route, so the production "/" has to
    # go before the debug one can take effect.
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/"]

    @app.on_event("startup")
    async def _seed_on_startup() -> None:
        await ensure_db()
        if not await seeder.is_seeded(DB_PATH):
            stats = await seeder.seed(DB_PATH)
            print(f"[devmode] seeded test data: {stats['ads']} ads, {stats['bids']} bids")
        else:
            restored = await seeder.rehydrate_channel(DB_PATH)
            print(f"[devmode] kept existing debug data, restored {restored} channel posts (--reset to reseed)")

    # HEAD included so readiness probes don't log a 405.
    @app.api_route("/", methods=["GET", "HEAD"])
    async def debug_index(request: Request) -> HTMLResponse:
        query = dict(request.query_params)
        user_key = resolve_user_key(query.get("as"))
        start_param = _start_param(query)

        config = {
            "initData": sign_init_data(user_key, start_param),
            "initDataUnsafe": init_data_unsafe(user_key, start_param),
            "currentUser": user_key,
            "users": user_directory(),
            "baseUrl": base_url,
            "startParam": start_param,
        }

        html = _read(os.path.join(WEBAPP_DIR, "index.html"))
        bootstrap = (
            f"<script>window.__DEBUG_TG__ = {json.dumps(config, ensure_ascii=False)};</script>\n"
            '    <script src="/__debug__/telegram-stub.js"></script>'
        )
        if TELEGRAM_SDK_TAG in html:
            html = html.replace(TELEGRAM_SDK_TAG, bootstrap, 1)
        else:
            # index.html changed shape — fall back to injecting before </head>.
            html = html.replace("</head>", f"{bootstrap}\n</head>", 1)
        return HTMLResponse(html, headers=NO_CACHE)

    @app.get("/__debug__/telegram-stub.js")
    async def debug_stub() -> Response:
        return Response(
            _read(os.path.join(STATIC_DIR, "telegram-stub.js")),
            media_type="application/javascript",
            headers=NO_CACHE,
        )

    @app.get("/__debug__/channel")
    async def debug_channel() -> HTMLResponse:
        return HTMLResponse(_read(os.path.join(STATIC_DIR, "channel.html")), headers=NO_CACHE)

    @app.get("/__debug__/outbox")
    async def debug_outbox() -> JSONResponse:
        return JSONResponse(fake.outbox.snapshot(), headers=NO_CACHE)

    @app.post("/__debug__/outbox/clear")
    async def debug_outbox_clear() -> Dict[str, Any]:
        fake.outbox.clear()
        return {"status": "cleared"}

    @app.get("/__debug__/photo/{file_id}")
    async def debug_photo(file_id: str, size: str = "full") -> Response:
        """Unauthenticated photo access for the debug channel viewer only."""
        data = fake.load_photo_bytes(file_id)
        if size == "thumb":
            try:
                from webserver.photos import _make_thumbnail

                data = _make_thumbnail(data)
            except Exception:
                pass
        return Response(content=data, media_type="image/jpeg", headers=NO_CACHE)

    @app.post("/__debug__/reseed")
    async def debug_reseed() -> Dict[str, Any]:
        await seeder.wipe(DB_PATH)
        stats = await seeder.seed(DB_PATH)
        return {"status": "reseeded", **stats}

    @app.get("/__debug__/state")
    async def debug_state() -> JSONResponse:
        return JSONResponse(
            {
                "db_path": DB_PATH,
                "base_url": base_url,
                "users": user_directory(),
                "events": len(fake.outbox.events),
                "channel_posts": len(fake.outbox.channel_posts),
            },
            headers=NO_CACHE,
        )

    return app


async def reset_debug_data() -> None:
    """Drop and reseed the debug database (used by run_debug.py --reset)."""
    from config import DB_PATH
    from devmode import seed as seeder
    from webserver.db import ensure_db

    await ensure_db()
    await seeder.wipe(DB_PATH)
    stats = await seeder.seed(DB_PATH)
    print(f"[devmode] reset: {stats['ads']} ads, {stats['bids']} bids")
