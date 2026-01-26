import hashlib
import hmac
import io
import json
import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional

import aiosqlite
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
import mimetypes
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from telegram import Bot, InputFile, InputMediaPhoto

import texts as texts_ru
from comments_manager import forward_thread_replies
from config import DB_PATH, PRIVATE_CHANNEL_ID, SLONSKI_ID
from utils import escape_markdown_custom, get_private_channel_post_link, get_serbia_time


load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s: %(message)s")

WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MEDIA_STORAGE_CHAT_ID = os.getenv("MEDIA_STORAGE_CHAT_ID")

logger = logging.getLogger("webapp")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(BOT_TOKEN)


class AnnouncementIn(BaseModel):
    description: str = Field(..., max_length=800)
    price: str = Field(..., max_length=130)
    photo_file_ids: List[str] = Field(default_factory=list)


class AnnouncementOut(BaseModel):
    id: int
    description: str
    price: str
    photo_file_ids: List[str]
    is_published: bool
    post_link: Optional[str] = None


def _parse_init_data(init_data: str) -> Dict[str, str]:
    return dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))


def _verify_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    data = _parse_init_data(init_data)
    received_hash = data.pop("hash", None)
    if not received_hash:
        logger.warning("auth: missing hash")
        raise HTTPException(status_code=401, detail="Missing hash")

    logger.debug("auth: fields=%s", ",".join(sorted(data.keys())))
    if LOG_LEVEL == "DEBUG" and bot_token:
        token_hash = hashlib.sha256(bot_token.encode()).hexdigest()[:12]
        logger.debug("auth: bot_token_sha256_prefix=%s", token_hash)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    # Telegram Web Apps use HMAC_SHA256 with key "WebAppData" over the bot token
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        logger.warning(
            "auth: invalid init data hash | calc=%s recv=%s",
            calculated_hash,
            received_hash,
        )
        raise HTTPException(status_code=401, detail="Invalid init data")

    user_raw = data.get("user")
    user = json.loads(user_raw) if user_raw else None
    if not user:
        logger.warning("auth: user not found in init data")
        raise HTTPException(status_code=401, detail="User not found")
    logger.info("auth: ok user_id=%s username=%s", user.get("id"), user.get("username"))
    return user


def _get_user_from_request(request: Request) -> Dict[str, Any]:
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("initData")
    if not init_data:
        logger.warning("auth: missing init data")
        raise HTTPException(status_code=401, detail="Missing init data")
    logger.debug("auth: init_data_len=%s", len(init_data))
    logger.debug("auth: init_data_prefix=%s", init_data[:64])
    return _verify_init_data(init_data, BOT_TOKEN)


def _format_announcement_text(
    description: str,
    price: str,
    username: str,
    user_display: Optional[str],
    is_updated: bool,
) -> str:
    description = escape_markdown_custom(description)
    price = escape_markdown_custom(price)

    if username != "None":
        contact_info = f"{texts_ru.CONTACT_TEXT}\n@{username.replace('_', '\\_')}"
    else:
        display = user_display or texts_ru.ANONYMOUS_NAME
        contact_info = f"{texts_ru.CONTACT_TEXT}\n{display.replace('_', '\\_')}"
    message = f"{description}\n\n"
    message += f"{texts_ru.PRICE_TEXT}\n{price}\n\n"
    message += contact_info

    if is_updated:
        current_time = get_serbia_time()
        message += f"\n\n{texts_ru.UPDATED_TEXT.format(current_time=current_time)}"

    return message


def _normalize_chat_id(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


app = FastAPI()
app.mount("/static", StaticFiles(directory=WEBAPP_DIR), name="static")


@app.on_event("startup")
async def _startup() -> None:
    await _ensure_db()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(WEBAPP_DIR, "index.html"))


async def _ensure_db() -> None:
    logger.info("db: ensure schema")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                description TEXT NOT NULL,
                price TEXT NOT NULL,
                photo_file_ids TEXT,
                message_ids TEXT,
                timestamp TEXT
            )
            """
        )
        await db.commit()


@app.get("/api/announcements")
async def list_announcements(user: Dict[str, Any] = Depends(_get_user_from_request)) -> Dict[str, Any]:
    user_id = user.get("id")
    logger.info("ann:list user_id=%s", user_id)
    items = []
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, description, price, photo_file_ids, message_ids FROM announcements WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()

    for row in rows:
        ann_id, description, price, photo_file_ids, message_ids = row
        photo_list = json.loads(photo_file_ids) if photo_file_ids else []
        message_list = json.loads(message_ids) if message_ids else []
        is_published = bool(message_list)
        private_channel_id = _normalize_chat_id(PRIVATE_CHANNEL_ID)
        post_link = (
            get_private_channel_post_link(private_channel_id, message_list[0])
            if is_published and private_channel_id is not None
            else None
        )
        items.append(
            AnnouncementOut(
                id=ann_id,
                description=description,
                price=price,
                photo_file_ids=photo_list,
                is_published=is_published,
                post_link=post_link,
            ).dict()
        )

    return {"items": items}


@app.post("/api/announcements")
async def create_announcement(
    payload: AnnouncementIn, user: Dict[str, Any] = Depends(_get_user_from_request)
) -> Dict[str, Any]:
    user_id = user.get("id")
    username = user.get("username") or "None"
    logger.info("ann:create user_id=%s username=%s desc_len=%s price_len=%s photos=%s",
                user_id, username, len(payload.description), len(payload.price), len(payload.photo_file_ids))

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO announcements (user_id, username, description, price, photo_file_ids)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, username, payload.description, payload.price, json.dumps(payload.photo_file_ids)),
        )
        await db.commit()
        ann_id = cursor.lastrowid

    return {"id": ann_id}


@app.put("/api/announcements/{ann_id}")
async def update_announcement(
    ann_id: int, payload: AnnouncementIn, user: Dict[str, Any] = Depends(_get_user_from_request)
) -> Dict[str, Any]:
    user_id = user.get("id")
    logger.info("ann:update user_id=%s ann_id=%s desc_len=%s price_len=%s photos=%s",
                user_id, ann_id, len(payload.description), len(payload.price), len(payload.photo_file_ids))
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id FROM announcements WHERE id = ? AND user_id = ?",
            (ann_id, user_id),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Announcement not found")

        await db.execute(
            """
            UPDATE announcements SET description = ?, price = ?, photo_file_ids = ?
            WHERE id = ?
            """,
            (payload.description, payload.price, json.dumps(payload.photo_file_ids), ann_id),
        )
        await db.commit()

    return {"id": ann_id}


@app.delete("/api/announcements/{ann_id}")
async def delete_announcement(ann_id: int, user: Dict[str, Any] = Depends(_get_user_from_request)) -> Dict[str, Any]:
    user_id = user.get("id")
    private_channel_id = _normalize_chat_id(PRIVATE_CHANNEL_ID)
    admin_id = _normalize_chat_id(SLONSKI_ID)
    logger.info("ann:delete user_id=%s ann_id=%s", user_id, ann_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT message_ids FROM announcements WHERE id = ? AND user_id = ?",
            (ann_id, user_id),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Announcement not found")

        message_ids = json.loads(row[0]) if row and row[0] else []

        if message_ids and private_channel_id is not None:
            for message_id in message_ids:
                try:
                    await bot.delete_message(chat_id=private_channel_id, message_id=message_id)
                except Exception as exc:
                    if admin_id is not None:
                        link = get_private_channel_post_link(private_channel_id, message_id)
                        await bot.send_message(
                            chat_id=admin_id,
                            text=(
                                "Не удалось удалить сообщение боту:\n"
                                f"Ссылка: {link}\n"
                                "Пожалуйста, удалите вручную."
                            ),
                        )
                    raise HTTPException(status_code=500, detail=str(exc))

        await db.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
        await db.commit()

    return {"status": "deleted"}


@app.post("/api/announcements/{ann_id}/publish")
async def publish_announcement(ann_id: int, user: Dict[str, Any] = Depends(_get_user_from_request)) -> Dict[str, Any]:
    user_id = user.get("id")
    private_channel_id = _normalize_chat_id(PRIVATE_CHANNEL_ID)
    admin_id = _normalize_chat_id(SLONSKI_ID)
    logger.info("ann:publish user_id=%s ann_id=%s", user_id, ann_id)

    if private_channel_id is None:
        raise HTTPException(status_code=500, detail="PRIVATE_CHANNEL_ID is not set")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT description, price, username, photo_file_ids, message_ids
            FROM announcements WHERE id = ? AND user_id = ?
            """,
            (ann_id, user_id),
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Announcement not found")

        description, price, username, photo_file_ids, message_ids_json = row
        photos = json.loads(photo_file_ids) if photo_file_ids else []
        old_message_ids = json.loads(message_ids_json) if message_ids_json else []

    is_editing = bool(old_message_ids)
    display_name = " ".join(
        filter(None, [user.get("first_name"), user.get("last_name")])
    ).strip() or None
    message = _format_announcement_text(
        description,
        price,
        username,
        display_name,
        is_updated=is_editing,
    )

    if photos:
        media = [
            InputMediaPhoto(photo_id, caption=message if idx == 0 else None, parse_mode="Markdown")
            for idx, photo_id in enumerate(photos)
        ]
        sent_messages = await bot.send_media_group(
            chat_id=private_channel_id, media=media, disable_notification=is_editing
        )
        new_message_ids = [msg.message_id for msg in sent_messages]
    else:
        sent_message = await bot.send_message(
            chat_id=private_channel_id,
            text=message,
            parse_mode="Markdown",
            disable_notification=is_editing,
        )
        new_message_ids = [sent_message.message_id]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE announcements SET message_ids = ?, timestamp = ? WHERE id = ?",
            (json.dumps(new_message_ids), get_serbia_time(), ann_id),
        )
        await db.commit()

    if is_editing and old_message_ids:
        try:
            await forward_thread_replies(old_message_ids[0], new_message_ids[0])
        except Exception:
            pass

        for message_id in old_message_ids:
            try:
                await bot.delete_message(chat_id=private_channel_id, message_id=message_id)
            except Exception as exc:
                if admin_id is not None:
                    link = get_private_channel_post_link(private_channel_id, message_id)
                    await bot.send_message(
                        chat_id=admin_id,
                        text=(
                            "Не удалось удалить сообщение боту:\n"
                            f"Ссылка: {link}\n"
                            "Пожалуйста, удалите вручную."
                        ),
                    )
                raise HTTPException(status_code=500, detail=str(exc))

    post_link = get_private_channel_post_link(private_channel_id, new_message_ids[0])
    logger.info("ann:publish done ann_id=%s post_link=%s", ann_id, post_link)
    return {"post_link": post_link}


@app.post("/api/uploads")
async def upload_files(
    files: List[UploadFile] = File(...),
    user: Dict[str, Any] = Depends(_get_user_from_request),
) -> Dict[str, Any]:
    if not MEDIA_STORAGE_CHAT_ID:
        raise HTTPException(status_code=500, detail="MEDIA_STORAGE_CHAT_ID is not set")

    storage_chat_id = _normalize_chat_id(MEDIA_STORAGE_CHAT_ID)
    if storage_chat_id is None:
        raise HTTPException(status_code=500, detail="Invalid MEDIA_STORAGE_CHAT_ID")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Too many files (max 10)")

    logger.info("upload:start user_id=%s files=%s", user.get("id"), len(files))
    file_ids = []
    for upload in files:
        data = await upload.read()
        filename = upload.filename or "photo.jpg"
        message = await bot.send_photo(
            chat_id=storage_chat_id,
            photo=InputFile(io.BytesIO(data), filename=filename),
        )
        if not message.photo:
            raise HTTPException(status_code=400, detail="Failed to upload photo")
        file_id = message.photo[-1].file_id
        file_ids.append(file_id)
        try:
            await bot.delete_message(chat_id=storage_chat_id, message_id=message.message_id)
        except Exception:
            pass

    logger.info("upload:done user_id=%s file_ids=%s", user.get("id"), len(file_ids))
    return {"file_ids": file_ids}


@app.get("/api/announcements/{ann_id}/photo")
async def get_announcement_photo(
    ann_id: int,
    file_id: str,
    user: Dict[str, Any] = Depends(_get_user_from_request),
) -> Response:
    user_id = user.get("id")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT photo_file_ids FROM announcements WHERE id = ? AND user_id = ?",
            (ann_id, user_id),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Announcement not found")

    photo_ids = json.loads(row[0]) if row[0] else []
    if file_id not in photo_ids:
        raise HTTPException(status_code=404, detail="Photo not found")

    tg_file = await bot.get_file(file_id)
    data = await tg_file.download_as_bytearray()
    content_type, _ = mimetypes.guess_type(tg_file.file_path or "")
    return Response(content=bytes(data), media_type=content_type or "image/jpeg")
