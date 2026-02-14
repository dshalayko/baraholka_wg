import json
import mimetypes
import uuid
from typing import Any, Dict, Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from telegram import InputMediaPhoto
from telegram.error import BadRequest, NetworkError, TelegramError, TimedOut

from comments_manager import forward_thread_replies
from config import DB_PATH, PRIVATE_CHANNEL_ID, SLONSKI_ID
from utils import get_private_channel_post_link, get_serbia_time
from webserver.auth import get_user_from_request
from webserver.models import AnnouncementIn, AnnouncementOut
from webserver.settings import logger
from webserver.telegram_client import bot, format_announcement_text, normalize_chat_id

router = APIRouter()


@router.get("/api/announcements")
async def list_announcements(user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    user_id = user.get("id")
    logger.info("ann:list user_id=%s", user_id)
    items = []
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, description, price, price_in_description, contact_info, photo_file_ids, message_ids, timestamp, last_published_is_edit
            FROM announcements WHERE user_id = ?
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()

    for row in rows:
        ann_id, description, price, price_in_description, contact_info, photo_file_ids, message_ids, timestamp, last_published_is_edit = row
        photo_list = json.loads(photo_file_ids) if photo_file_ids else []
        message_list = json.loads(message_ids) if message_ids else []
        is_published = bool(message_list)
        is_updated = bool(last_published_is_edit) if is_published else False
        private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
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
                price_in_description=bool(price_in_description),
                contact_info=contact_info,
                photo_file_ids=photo_list,
                is_published=is_published,
                post_link=post_link,
                published_at=timestamp if is_published else None,
                is_updated=is_updated,
            ).dict()
        )

    return {"items": items}


@router.post("/api/announcements")
async def create_announcement(
    payload: AnnouncementIn, user: Dict[str, Any] = Depends(get_user_from_request)
) -> Dict[str, Any]:
    user_id = user.get("id")
    username = user.get("username") or "None"
    price = payload.price or ""
    price_in_description = bool(payload.price_in_description)
    contact_info = (payload.contact_info or "").strip()
    if username == "None" and not contact_info:
        raise HTTPException(status_code=422, detail="Contact info is required when username is missing")
    if not price_in_description and not price.strip():
        raise HTTPException(status_code=422, detail="Price is required unless price_in_description is true")
    logger.info(
        "ann:create user_id=%s username=%s desc_len=%s price_len=%s price_in_desc=%s contact_len=%s photos=%s",
        user_id,
        username,
        len(payload.description),
        len(price),
        price_in_description,
        len(contact_info),
        len(payload.photo_file_ids),
    )

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO announcements (user_id, username, description, price, price_in_description, contact_info, photo_file_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                payload.description,
                price,
                1 if price_in_description else 0,
                contact_info,
                json.dumps(payload.photo_file_ids),
            ),
        )
        await db.commit()
        ann_id = cursor.lastrowid

    return {"id": ann_id}


@router.put("/api/announcements/{ann_id}")
async def update_announcement(
    ann_id: int, payload: AnnouncementIn, user: Dict[str, Any] = Depends(get_user_from_request)
) -> Dict[str, Any]:
    user_id = user.get("id")
    price = payload.price or ""
    price_in_description = bool(payload.price_in_description)
    contact_info = (payload.contact_info or "").strip()
    username = user.get("username") or "None"
    if username == "None" and not contact_info:
        raise HTTPException(status_code=422, detail="Contact info is required when username is missing")
    if not price_in_description and not price.strip():
        raise HTTPException(status_code=422, detail="Price is required unless price_in_description is true")
    logger.info(
        "ann:update user_id=%s ann_id=%s desc_len=%s price_len=%s price_in_desc=%s contact_len=%s photos=%s",
        user_id,
        ann_id,
        len(payload.description),
        len(price),
        price_in_description,
        len(contact_info),
        len(payload.photo_file_ids),
    )
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
            UPDATE announcements SET description = ?, price = ?, price_in_description = ?, contact_info = ?, photo_file_ids = ?
            WHERE id = ?
            """,
            (
                payload.description,
                price,
                1 if price_in_description else 0,
                contact_info,
                json.dumps(payload.photo_file_ids),
                ann_id,
            ),
        )
        await db.commit()

    return {"id": ann_id}


@router.delete("/api/announcements/{ann_id}")
async def delete_announcement(ann_id: int, user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    user_id = user.get("id")
    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
    admin_id = normalize_chat_id(SLONSKI_ID)
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
        post_link = (
            get_private_channel_post_link(private_channel_id, message_ids[0])
            if message_ids and private_channel_id is not None
            else None
        )
        not_deleted_ids = []

        if message_ids and private_channel_id is not None:
            for message_id in message_ids:
                try:
                    await bot.delete_message(chat_id=private_channel_id, message_id=message_id)
                except BadRequest as exc:
                    exc_text = str(exc).lower()
                    if "message to delete not found" in exc_text or "message not found" in exc_text:
                        logger.warning(
                            "ann:delete message not found chat_id=%s message_id=%s",
                            private_channel_id,
                            message_id,
                        )
                        continue
                    if "message can't be deleted" in exc_text or "message cannot be deleted" in exc_text:
                        logger.warning(
                            "ann:delete not allowed chat_id=%s message_id=%s",
                            private_channel_id,
                            message_id,
                        )
                        not_deleted_ids.append(message_id)
                        if admin_id is not None:
                            link = get_private_channel_post_link(private_channel_id, message_id)
                            await bot.send_message(
                                chat_id=admin_id,
                                text=(
                                    "Сообщение не удалось удалить (ограничение Telegram):\n"
                                    f"Ссылка: {link}\n"
                                    f"Ошибка: {exc}\n"
                                    "Пожалуйста, удалите вручную."
                                ),
                            )
                        continue
                    error_id = uuid.uuid4().hex[:8]
                    logger.exception(
                        "ann:delete failed error_id=%s user_id=%s ann_id=%s chat_id=%s message_id=%s",
                        error_id,
                        user_id,
                        ann_id,
                        private_channel_id,
                        message_id,
                    )
                    if admin_id is not None:
                        link = get_private_channel_post_link(private_channel_id, message_id)
                        await bot.send_message(
                            chat_id=admin_id,
                            text=(
                                "Не удалось удалить сообщение боту:\n"
                                f"Ссылка: {link}\n"
                                f"Ошибка: {exc}\n"
                                f"Код ошибки: {error_id}\n"
                                "Пожалуйста, удалите вручную."
                            ),
                        )
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "message": "Failed to delete announcement.",
                            "error_id": error_id,
                            "error_detail": str(exc),
                            "ann_id": ann_id,
                        },
                    )
                except TelegramError as exc:
                    error_id = uuid.uuid4().hex[:8]
                    logger.exception(
                        "ann:delete failed error_id=%s user_id=%s ann_id=%s chat_id=%s message_id=%s",
                        error_id,
                        user_id,
                        ann_id,
                        private_channel_id,
                        message_id,
                    )
                    if admin_id is not None:
                        link = get_private_channel_post_link(private_channel_id, message_id)
                        await bot.send_message(
                            chat_id=admin_id,
                            text=(
                                "Не удалось удалить сообщение боту:\n"
                                f"Ссылка: {link}\n"
                                f"Ошибка: {exc}\n"
                                f"Код ошибки: {error_id}\n"
                                "Пожалуйста, удалите вручную."
                            ),
                        )
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "message": "Failed to delete announcement.",
                            "error_id": error_id,
                            "error_detail": str(exc),
                            "ann_id": ann_id,
                        },
                    )

        await db.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
        await db.commit()

    response = {"status": "deleted"}
    if not_deleted_ids:
        response["warning"] = "Post in channel could not be deleted."
        response["not_deleted_message_ids"] = not_deleted_ids
        if post_link:
            response["post_link"] = post_link
    return response


@router.post("/api/announcements/{ann_id}/publish")
async def publish_announcement(ann_id: int, user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    user_id = user.get("id")
    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
    admin_id = normalize_chat_id(SLONSKI_ID)
    logger.info("ann:publish user_id=%s ann_id=%s", user_id, ann_id)

    if private_channel_id is None:
        raise HTTPException(status_code=500, detail="PRIVATE_CHANNEL_ID is not set")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT description, price, price_in_description, username, contact_info, photo_file_ids, message_ids
            FROM announcements WHERE id = ? AND user_id = ?
            """,
            (ann_id, user_id),
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Announcement not found")

        description, price, price_in_description, username, contact_info, photo_file_ids, message_ids_json = row
        photos = json.loads(photo_file_ids) if photo_file_ids else []
        old_message_ids = json.loads(message_ids_json) if message_ids_json else []

    is_editing = bool(old_message_ids)
    display_name = " ".join(
        filter(None, [user.get("first_name"), user.get("last_name")])
    ).strip() or None
    message = format_announcement_text(
        description,
        price,
        bool(price_in_description),
        username,
        contact_info,
        display_name,
        is_updated=is_editing,
    )

    if photos:
        media = [
            InputMediaPhoto(photo_id, caption=message if idx == 0 else None, parse_mode="MarkdownV2")
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
            parse_mode="MarkdownV2",
            disable_notification=is_editing,
        )
        new_message_ids = [sent_message.message_id]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE announcements SET message_ids = ?, timestamp = ?, last_published_is_edit = ? WHERE id = ?",
            (json.dumps(new_message_ids), get_serbia_time(), 1 if is_editing else 0, ann_id),
        )
        await db.commit()

    if is_editing and old_message_ids:
        transfer_success = await forward_thread_replies(old_message_ids[0], new_message_ids[0])
        if not transfer_success:
            logger.warning(
                "ann:publish comments transfer failed ann_id=%s old_message_id=%s new_message_id=%s",
                ann_id,
                old_message_ids[0],
                new_message_ids[0],
            )

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


@router.get("/api/announcements/{ann_id}/photo")
async def get_announcement_photo(
    ann_id: int,
    file_id: str,
    user: Dict[str, Any] = Depends(get_user_from_request),
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

    content_type, _ = mimetypes.guess_type(tg_file.file_path or "")
    return Response(content=bytes(data), media_type=content_type or "image/jpeg")
