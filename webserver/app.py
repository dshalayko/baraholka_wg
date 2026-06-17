import asyncio
import json
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

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


@app.on_event("startup")
async def _startup() -> None:
    await ensure_db()
    asyncio.create_task(_run_auction_job())


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(WEBAPP_DIR, "index.html"), headers=NO_CACHE_HEADERS)


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
