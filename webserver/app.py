import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from webserver.db import ensure_db
from webserver.routes.announcements import router as announcements_router
from webserver.routes.bugs import router as bugs_router
from webserver.routes.stats import router as stats_router
from webserver.routes.uploads import router as uploads_router
from webserver.settings import FAVICON_SVG, WEBAPP_DIR


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


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(WEBAPP_DIR, "index.html"), headers=NO_CACHE_HEADERS)


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(content=FAVICON_SVG, media_type="image/svg+xml")


app.include_router(announcements_router)
app.include_router(uploads_router)
app.include_router(bugs_router)
app.include_router(stats_router)
