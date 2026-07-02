import asyncio
import hashlib
import io
import mimetypes
import os
import uuid

from fastapi import HTTPException
from fastapi.responses import Response
from telegram.error import BadRequest, NetworkError, TelegramError, TimedOut

from webserver.settings import BASE_DIR, logger
from webserver.telegram_client import bot

THUMB_MAX_EDGE = 320
THUMB_JPEG_QUALITY = 78
THUMB_CACHE_DIR = os.path.join(BASE_DIR, "data", "photo_cache")

# A Telegram file_id is immutable — the same id always resolves to the same
# bytes — so browsers may cache photo responses indefinitely.
PHOTO_CACHE_HEADERS = {"Cache-Control": "private, max-age=31536000, immutable"}


def _thumb_cache_path(file_id: str) -> str:
    digest = hashlib.sha256(file_id.encode()).hexdigest()
    return os.path.join(THUMB_CACHE_DIR, f"{digest}_thumb{THUMB_MAX_EDGE}.jpg")


def _make_thumbnail(data: bytes) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((THUMB_MAX_EDGE, THUMB_MAX_EDGE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=THUMB_JPEG_QUALITY)
    return out.getvalue()


def _store_thumb(cache_path: str, thumb: bytes) -> None:
    # Write via a unique temp name + atomic rename so concurrent requests for
    # the same photo can't observe (or produce) a half-written cache file.
    os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
    tmp_path = f"{cache_path}.{uuid.uuid4().hex}.tmp"
    with open(tmp_path, "wb") as fh:
        fh.write(thumb)
    os.replace(tmp_path, cache_path)


async def serve_telegram_photo(file_id: str, size: str = "full") -> Response:
    """Download a photo from Telegram and return it as an HTTP response.

    size="thumb" serves a small JPEG (long edge THUMB_MAX_EDGE px) resized on
    first request and cached on disk forever; anything else serves the
    original. Callers are responsible for authorization and for checking that
    file_id belongs to the requested announcement.
    """
    want_thumb = size == "thumb"

    if want_thumb:
        cache_path = _thumb_cache_path(file_id)
        try:
            with open(cache_path, "rb") as fh:
                return Response(content=fh.read(), media_type="image/jpeg", headers=PHOTO_CACHE_HEADERS)
        except FileNotFoundError:
            pass

    try:
        tg_file = await bot.get_file(file_id)
        data = await tg_file.download_as_bytearray()
    except BadRequest as exc:
        exc_text = str(exc).lower()
        if "temporarily unavailable" in exc_text:
            raise HTTPException(status_code=503, detail="Photo temporarily unavailable")
        if "wrong file_id" in exc_text or "file_id" in exc_text:
            raise HTTPException(status_code=404, detail="Photo not found")
        raise HTTPException(status_code=502, detail=str(exc))
    except (TimedOut, NetworkError) as exc:
        raise HTTPException(status_code=503, detail=f"Telegram timeout: {exc}")
    except TelegramError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if want_thumb:
        try:
            thumb = await asyncio.to_thread(_make_thumbnail, bytes(data))
        except Exception as exc:
            # Fall back to the original bytes rather than failing the request.
            logger.warning("photo:thumbnail failed file_id=%s error=%s", file_id, exc)
        else:
            try:
                _store_thumb(cache_path, thumb)
            except OSError as exc:
                logger.warning("photo:thumb cache write failed error=%s", exc)
            return Response(content=thumb, media_type="image/jpeg", headers=PHOTO_CACHE_HEADERS)

    content_type, _ = mimetypes.guess_type(tg_file.file_path or "")
    return Response(content=bytes(data), media_type=content_type or "image/jpeg", headers=PHOTO_CACHE_HEADERS)
