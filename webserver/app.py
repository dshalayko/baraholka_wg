import asyncio
import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from version import APP_VERSION
from webserver.auth import get_user_from_request
from webserver.db import ensure_db
from webserver.routes.announcements import router as announcements_router
from webserver.routes.auctions import router as auctions_router
from webserver.routes.bugs import router as bugs_router
from webserver.routes.stats import router as stats_router
from webserver.routes.uploads import router as uploads_router
from webserver.settings import FAVICON_SVG, WEBAPP_DIR, WEBAPP_URL, logger


NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if getattr(response, "status_code", 200) == 200:
            response.headers.update(NO_CACHE_HEADERS)
        return response


app = FastAPI()
app.mount("/static", NoCacheStaticFiles(directory=WEBAPP_DIR), name="static")

MAX_JSON_BODY_BYTES = 2 * 1024 * 1024
# Uploads: up to 10 photos × 10 MB each, plus multipart overhead.
MAX_UPLOAD_BODY_BYTES = 110 * 1024 * 1024


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    # Handlers read the whole body into memory, so an unbounded body is a
    # memory-DoS vector; reject oversized (or undeclared chunked) bodies early.
    if request.method in ("POST", "PUT", "PATCH"):
        limit = MAX_UPLOAD_BODY_BYTES if request.url.path == "/api/uploads" else MAX_JSON_BODY_BYTES
        content_length = request.headers.get("content-length")
        if content_length is None:
            if request.headers.get("transfer-encoding"):
                return JSONResponse({"detail": "Content-Length required"}, status_code=411)
        else:
            try:
                declared = int(content_length)
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
            if declared > limit:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
    return await call_next(request)


@app.on_event("startup")
async def _startup() -> None:
    await ensure_db()
    asyncio.create_task(_run_auction_job())


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(WEBAPP_DIR, "index.html"), headers=NO_CACHE_HEADERS)


@app.get("/api/version")
async def version(request: Request) -> JSONResponse:
    # Authed like the rest of /api: the branch and commit of the running deploy
    # are not something to hand out to anonymous callers.
    get_user_from_request(request)
    return JSONResponse({"version": APP_VERSION}, headers=NO_CACHE_HEADERS)


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(content=FAVICON_SVG, media_type="image/svg+xml")


async def _finish_expired_auctions() -> None:
    import aiosqlite
    import pytz
    from datetime import datetime
    from config import DB_PATH
    from webserver.routes.auctions import finish_auction

    belgrade_tz = pytz.timezone("Europe/Belgrade")
    now_str = datetime.now(pytz.utc).astimezone(belgrade_tz).strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id FROM announcements
            WHERE COALESCE(ad_type,'fixed') = 'auction'
              AND auction_status = 'active'
              AND auction_end_at <= ?
            """,
            (now_str,),
        )
        expired_ids = [r[0] for r in await cursor.fetchall()]

    for ann_id in expired_ids:
        try:
            await finish_auction(ann_id)
        except Exception as exc:
            logger.warning("auction:finish failed ann_id=%s error=%s", ann_id, exc)


async def _run_auction_job() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await _finish_expired_auctions()
        except Exception as exc:
            logger.exception("auction:job error: %s", exc)


app.include_router(announcements_router)
app.include_router(auctions_router)
app.include_router(uploads_router)
app.include_router(bugs_router)
app.include_router(stats_router)
