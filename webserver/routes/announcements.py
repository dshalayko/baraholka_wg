import json
import mimetypes
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiosqlite
import pytz
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from telegram import InputMediaPhoto
from telegram.error import BadRequest, NetworkError, TelegramError, TimedOut

from comments_manager import delete_channel_messages, forward_thread_replies, get_discussion_replies_counts
from config import DB_PATH, PRIVATE_CHANNEL_ID, SLONSKI_ID
from utils import get_private_channel_post_link, get_serbia_time, is_timestamp_older_than_days, parse_timestamp
from webserver.auth import get_user_from_request
from webserver.models import AnnouncementIn, AnnouncementOut
from webserver.routes.stats import increment_stat
from webserver.settings import BUG_CHAT_ID, WEBAPP_URL, logger
from webserver.telegram_client import bot, format_announcement_text, format_auction_text, make_bid_link_md, normalize_chat_id, normalize_currency

router = APIRouter()

# An auction may last at most 2 days minus 10 minutes (safety margin under 48h).
MAX_AUCTION_DURATION = timedelta(days=2) - timedelta(minutes=10)


async def send_bug_report(
    *,
    action: str,
    user: Dict[str, Any],
    ann_id: Optional[int],
    status: str,
    message: str,
    detail: Optional[str],
    post_link: Optional[str] = None,
    error_id: Optional[str] = None,
) -> None:
    bug_chat_id = normalize_chat_id(BUG_CHAT_ID)
    if bug_chat_id is None:
        return

    user_id = user.get("id")
    try:
        await bot.send_message(
            chat_id=bug_chat_id,
            text=(
                "BUG REPORT\n"
                f"Time: {get_serbia_time()}\n"
                f"User ID: {user_id}\n"
                f"Username: {user.get('username') or 'None'}\n"
                f"Name: {' '.join(filter(None, [user.get('first_name'), user.get('last_name')])).strip() or 'None'}\n"
                f"Action: {action}\n"
                f"Ad ID: {ann_id}\n"
                f"Status: {status}\n"
                f"Error ID: {error_id}\n"
                f"Message: {message}\n"
                f"Detail: {detail}\n"
                f"Post link: {post_link}\n"
                "Client time: None\n"
                "Language: None\n"
                "User-Agent: None\n"
            ),
        )
    except Exception:
        logger.exception("bug-report auto send failed action=%s ann_id=%s user_id=%s", action, ann_id, user_id)


@router.get("/api/announcements")
async def list_announcements(user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    user_id = user.get("id")
    logger.info("ann:list user_id=%s", user_id)
    items = []
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, description, price, price_in_description, contact_info, photo_file_ids, message_ids, timestamp, updated_at, last_published_is_edit, is_reserved,
                   COALESCE(ad_type,'fixed'), auction_status, start_price, current_price, min_step, auction_end_at, winner_username, auction_duration_hours, currency,
                   (SELECT COUNT(*) FROM auction_bids WHERE announcement_id = announcements.id) as bids_count
            FROM announcements WHERE user_id = ?
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()

    published_root_message_ids = []
    pending_items = []

    for row in rows:
        (
            ann_id,
            description,
            price,
            price_in_description,
            contact_info,
            photo_file_ids,
            message_ids,
            timestamp,
            updated_at,
            last_published_is_edit,
            is_reserved,
            ad_type,
            auction_status,
            start_price,
            current_price,
            min_step,
            auction_end_at,
            winner_username,
            auction_duration_hours,
            currency,
            bids_count,
        ) = row
        photo_list = json.loads(photo_file_ids) if photo_file_ids else []
        message_list = json.loads(message_ids) if message_ids else []
        is_published = bool(message_list)
        is_updated = bool(last_published_is_edit) if is_published else False
        root_message_id = message_list[0] if is_published else None
        if root_message_id:
            published_root_message_ids.append(root_message_id)
        private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
        post_link = (
            get_private_channel_post_link(private_channel_id, message_list[0])
            if is_published and private_channel_id is not None
            else None
        )
        pending_items.append(
            {
                "id": ann_id,
                "description": description,
                "price": price,
                "price_in_description": bool(price_in_description),
                "contact_info": contact_info,
                "photo_file_ids": photo_list,
                "is_published": is_published,
                "post_link": post_link,
                "published_at": timestamp if is_published else None,
                "updated_at": updated_at,
                "is_updated": is_updated,
                "is_reserved": bool(is_reserved),
                "ad_type": ad_type or "fixed",
                "auction_status": auction_status,
                "start_price": start_price,
                "current_price": current_price,
                "min_step": min_step,
                "auction_end_at": auction_end_at,
                "winner_username": winner_username,
                "auction_duration_hours": auction_duration_hours,
                "currency": currency or "RSD",
                "bids_count": bids_count or 0,
                "_root_message_id": root_message_id,
            }
        )

    comments_counts = await get_discussion_replies_counts(published_root_message_ids) if published_root_message_ids else {}
    for item in pending_items:
        root_message_id = item.pop("_root_message_id", None)
        item["comments_count"] = comments_counts.get(root_message_id, 0) if root_message_id else 0
        items.append(AnnouncementOut(**item).dict())
    
    def _sort_dt(raw: Dict[str, Any]) -> datetime:
        return parse_timestamp(raw.get("updated_at")) or parse_timestamp(raw.get("published_at")) or datetime.min

    items.sort(
        key=lambda item: (_sort_dt(item), item.get("id", 0)),
        reverse=True,
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
    if not price_in_description and not price.strip() and payload.ad_type != "auction":
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

    # For auctions only the duration is stored on create; the actual end time is
    # computed at publish, so a saved draft doesn't expire before it goes live.
    ad_type = payload.ad_type or "fixed"
    auction_duration_hours = payload.auction_duration_hours if ad_type == "auction" else None
    currency = normalize_currency(payload.currency) if ad_type == "auction" else None

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO announcements (user_id, username, description, price, price_in_description, contact_info, photo_file_ids, updated_at, ad_type, start_price, min_step, auction_duration_hours, owner_language_code, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                payload.description,
                price,
                1 if price_in_description else 0,
                contact_info,
                json.dumps(payload.photo_file_ids),
                get_serbia_time(),
                ad_type,
                payload.start_price if ad_type == "auction" else None,
                payload.min_step if ad_type == "auction" else None,
                auction_duration_hours,
                user.get("language_code"),
                currency,
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
    if not price_in_description and not price.strip() and payload.ad_type != "auction":
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
            "SELECT message_ids FROM announcements WHERE id = ? AND user_id = ?",
            (ann_id, user_id),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Announcement not found")
        is_published = bool(json.loads(row[0]) if row[0] else [])

        # Auctions store the duration; for a draft the end time is finalized at
        # publish. For an already-published (running) auction, editing sets a new
        # end time = now + chosen duration so the deadline actually changes.
        update_ad_type = payload.ad_type or "fixed"
        update_duration = payload.auction_duration_hours if update_ad_type == "auction" else None
        update_currency = normalize_currency(payload.currency) if update_ad_type == "auction" else None
        new_end_at = None
        if update_ad_type == "auction" and is_published and payload.auction_duration_hours:
            belgrade_tz = pytz.timezone("Europe/Belgrade")
            now = datetime.now(pytz.utc).astimezone(belgrade_tz)
            end_dt = min(now + timedelta(hours=payload.auction_duration_hours), now + MAX_AUCTION_DURATION)
            new_end_at = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        await db.execute(
            """
            UPDATE announcements SET description = ?, price = ?, price_in_description = ?, contact_info = ?, photo_file_ids = ?, updated_at = ?,
                ad_type = ?, start_price = COALESCE(?, start_price), min_step = ?, auction_duration_hours = COALESCE(?, auction_duration_hours),
                auction_end_at = COALESCE(?, auction_end_at), currency = COALESCE(?, currency)
            WHERE id = ?
            """,
            (
                payload.description,
                price,
                1 if price_in_description else 0,
                contact_info,
                json.dumps(payload.photo_file_ids),
                get_serbia_time(),
                update_ad_type,
                payload.start_price if update_ad_type == "auction" else None,
                payload.min_step if update_ad_type == "auction" else None,
                update_duration,
                new_end_at,
                update_currency,
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
            # User account first (no 48h Bot API limit); bot handles any leftovers.
            remaining_to_delete = await delete_channel_messages(message_ids)
            for message_id in remaining_to_delete:
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
    try:
        user_id = user.get("id")
        private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
        admin_id = normalize_chat_id(SLONSKI_ID)
        bug_chat_id = normalize_chat_id(BUG_CHAT_ID)
        logger.info("ann:publish user_id=%s ann_id=%s", user_id, ann_id)

        if private_channel_id is None:
            raise HTTPException(status_code=500, detail="PRIVATE_CHANNEL_ID is not set")

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT description, price, price_in_description, username, contact_info, photo_file_ids, message_ids, timestamp, is_reserved,
                       COALESCE(ad_type,'fixed'), auction_status, start_price, min_step, auction_end_at, auction_duration_hours,
                       current_price, winner_username, currency
                FROM announcements WHERE id = ? AND user_id = ?
                """,
                (ann_id, user_id),
            )
            row = await cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Announcement not found")

            (
                description,
                price,
                price_in_description,
                username,
                contact_info,
                photo_file_ids,
                message_ids_json,
                previous_timestamp,
                is_reserved,
                pub_ad_type,
                pub_auction_status,
                pub_start_price,
                pub_min_step,
                pub_auction_end_at,
                pub_auction_duration_hours,
                pub_current_price,
                pub_winner_username,
                pub_currency,
            ) = row
            photos = json.loads(photo_file_ids) if photo_file_ids else []
            old_message_ids = json.loads(message_ids_json) if message_ids_json else []

        is_editing = bool(old_message_ids)
        # Finalize the auction end time at publish: compute from the stored
        # duration for a first publish; keep the existing end on republish so
        # editing a live auction doesn't extend it.
        if pub_ad_type == "auction" and (not is_editing or not pub_auction_end_at):
            belgrade_tz = pytz.timezone("Europe/Belgrade")
            now = datetime.now(pytz.utc).astimezone(belgrade_tz)
            duration_hours = pub_auction_duration_hours or 24
            end_dt = min(now + timedelta(hours=duration_hours), now + MAX_AUCTION_DURATION)
            pub_auction_end_at = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        show_updated_label = is_editing and is_timestamp_older_than_days(previous_timestamp, 2)
        display_name = " ".join(
            filter(None, [user.get("first_name"), user.get("last_name")])
        ).strip() or None

        is_auction = pub_ad_type == "auction"
        logger.info(
            "ann:publish type=%s is_auction=%s photos=%s start_price=%s min_step=%s end_at=%s webapp_url=%s",
            pub_ad_type, is_auction, len(photos), pub_start_price, pub_min_step, pub_auction_end_at, WEBAPP_URL,
        )

        if is_auction:
            # The publisher is the owner — the post is localized to their language.
            owner_language_code = user.get("language_code")
            logger.info("ann:publish auction step=format_text ann_id=%s lang=%s", ann_id, owner_language_code)
            message = format_auction_text(
                description=description,
                username=username,
                contact_info=contact_info,
                user_display=display_name,
                start_price=pub_start_price,
                current_price=pub_current_price,
                min_step=pub_min_step,
                auction_end_at=pub_auction_end_at,
                winner_username=pub_winner_username,
                auction_status="active",
                language_code=owner_language_code,
                currency=pub_currency,
            )
            # Telegram does not allow inline buttons on media groups (albums), so the
            # bid action is a clickable link inside the caption. This keeps everything
            # — all photos + text + bid link — in a single message.
            logger.info("ann:publish auction bid_link ann_id=%s", ann_id)
            message = message + "\n\n" + make_bid_link_md(ann_id, owner_language_code)
            if photos:
                logger.info("ann:publish auction step=send_media_group ann_id=%s photos=%s", ann_id, len(photos))
                media = [
                    InputMediaPhoto(photo_id, caption=message if idx == 0 else None, parse_mode="MarkdownV2")
                    for idx, photo_id in enumerate(photos)
                ]
                sent_media = await bot.send_media_group(
                    chat_id=private_channel_id, media=media, disable_notification=is_editing
                )
                new_message_ids = [msg.message_id for msg in sent_media]
            else:
                logger.info("ann:publish auction step=send_text_only ann_id=%s", ann_id)
                sent_message = await bot.send_message(
                    chat_id=private_channel_id,
                    text=message,
                    parse_mode="MarkdownV2",
                    disable_notification=is_editing,
                )
                new_message_ids = [sent_message.message_id]

            logger.info("ann:publish auction step=db_update ann_id=%s message_ids=%s", ann_id, new_message_ids)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE announcements SET message_ids = ?, timestamp = ?, updated_at = ?, last_published_is_edit = 0, auction_status = 'active', owner_language_code = ?, auction_end_at = ? WHERE id = ?",
                    (json.dumps(new_message_ids), get_serbia_time(), get_serbia_time(), owner_language_code, pub_auction_end_at, ann_id),
                )
                await db.commit()
            logger.info("ann:publish auction step=done ann_id=%s", ann_id)
        else:
            message = format_announcement_text(
                description,
                price,
                bool(price_in_description),
                username,
                contact_info,
                display_name,
                is_updated=show_updated_label,
                is_reserved=bool(is_reserved),
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
                    "UPDATE announcements SET message_ids = ?, timestamp = ?, updated_at = ?, last_published_is_edit = ? WHERE id = ?",
                    (json.dumps(new_message_ids), get_serbia_time(), get_serbia_time(), 1 if show_updated_label else 0, ann_id),
                )
                await db.commit()

        delete_failures: list[str] = []
        if is_editing and old_message_ids:
            transfer_success = await forward_thread_replies(old_message_ids[0], new_message_ids[0])
            if not transfer_success:
                logger.warning(
                    "ann:publish comments transfer failed ann_id=%s old_message_id=%s new_message_id=%s",
                    ann_id,
                    old_message_ids[0],
                    new_message_ids[0],
                )

            # Delete old posts via the user account first (no 48h Bot API limit),
            # then fall back to the bot for anything that's left.
            remaining_to_delete = await delete_channel_messages(old_message_ids)
            for message_id in remaining_to_delete:
                try:
                    await bot.delete_message(chat_id=private_channel_id, message_id=message_id)
                except Exception as exc:
                    link = get_private_channel_post_link(private_channel_id, message_id)
                    delete_failures.append(f"{message_id} ({link}) -> {exc}")
                    logger.warning(
                        "ann:publish old message delete failed user_id=%s ann_id=%s message_id=%s error=%s",
                        user_id,
                        ann_id,
                        message_id,
                        exc,
                    )
            if delete_failures and admin_id is not None:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=(
                            "Не удалось удалить старые сообщения при обновлении объявления:\n"
                            f"ann_id: {ann_id}\n"
                            f"user_id: {user_id}\n"
                            f"details:\n- " + "\n- ".join(delete_failures) + "\n"
                            "Пожалуйста, удалите вручную."
                        ),
                    )
                except Exception:
                    logger.exception("ann:publish failed to notify admin delete issues ann_id=%s", ann_id)
            if delete_failures and bug_chat_id is not None:
                try:
                    await bot.send_message(
                        chat_id=bug_chat_id,
                        text=(
                            "BUG REPORT\n"
                            f"Time: {get_serbia_time()}\n"
                            f"User ID: {user_id}\n"
                            f"Username: {user.get('username') or 'None'}\n"
                            f"Name: {' '.join(filter(None, [user.get('first_name'), user.get('last_name')])).strip() or 'None'}\n"
                            "Action: publish_ad_old_message_delete\n"
                            f"Ad ID: {ann_id}\n"
                            "Status: warning\n"
                            "Error ID: None\n"
                            "Message: Failed to delete old message(s) after publish. Publish completed.\n"
                            f"Detail: {'; '.join(delete_failures)}\n"
                            f"Post link: {get_private_channel_post_link(private_channel_id, new_message_ids[0])}\n"
                            "Client time: None\n"
                            "Language: None\n"
                            "User-Agent: None\n"
                        ),
                    )
                except Exception:
                    logger.exception("ann:publish failed to send bug report ann_id=%s", ann_id)

        post_link = get_private_channel_post_link(private_channel_id, new_message_ids[0])
        logger.info("ann:publish done ann_id=%s post_link=%s", ann_id, post_link)
        await increment_stat("publish_success")
        return {"post_link": post_link}
    except (TimedOut, NetworkError) as exc:
        await increment_stat("publish_fail")
        logger.warning("ann:publish telegram_timeout ann_id=%s user_id=%s error=%s", ann_id, user.get("id"), exc)
        raise HTTPException(status_code=504, detail=f"Telegram timeout while publishing: {exc}")
    except HTTPException:
        raise
    except Exception as exc:
        await increment_stat("publish_fail")
        logger.exception("ann:publish UNHANDLED EXCEPTION ann_id=%s user_id=%s error=%s", ann_id, user.get("id"), exc)
        raise HTTPException(status_code=500, detail=f"Publish failed: {type(exc).__name__}: {exc}")


@router.post("/api/announcements/{ann_id}/reserve")
async def reserve_announcement(ann_id: int, user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    user_id = user.get("id")
    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
    logger.info("ann:reserve user_id=%s ann_id=%s", user_id, ann_id)

    if private_channel_id is None:
        raise HTTPException(status_code=500, detail="PRIVATE_CHANNEL_ID is not set")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT description, price, price_in_description, username, contact_info, photo_file_ids, message_ids, is_reserved
            FROM announcements WHERE id = ? AND user_id = ?
            """,
            (ann_id, user_id),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Announcement not found")

        (
            description,
            price,
            price_in_description,
            username,
            contact_info,
            photo_file_ids,
            message_ids_json,
            is_reserved,
        ) = row
        message_ids = json.loads(message_ids_json) if message_ids_json else []
        if not message_ids:
            raise HTTPException(status_code=400, detail="Only published announcements can be reserved")
        photos = json.loads(photo_file_ids) if photo_file_ids else []
        new_is_reserved = not bool(is_reserved)

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
        is_updated=False,
        is_reserved=new_is_reserved,
    )

    try:
        if photos:
            await bot.edit_message_caption(
                chat_id=private_channel_id,
                message_id=message_ids[0],
                caption=message,
                parse_mode="MarkdownV2",
            )
        else:
            await bot.edit_message_text(
                chat_id=private_channel_id,
                message_id=message_ids[0],
                text=message,
                parse_mode="MarkdownV2",
            )
    except (TimedOut, NetworkError) as exc:
        error_id = uuid.uuid4().hex[:8]
        post_link = get_private_channel_post_link(private_channel_id, message_ids[0])
        logger.warning("ann:reserve telegram_timeout ann_id=%s user_id=%s error=%s", ann_id, user_id, exc)
        await send_bug_report(
            action="reserve_ad",
            user=user,
            ann_id=ann_id,
            status="error",
            error_id=error_id,
            message="Telegram timeout while updating reservation.",
            detail=str(exc),
            post_link=post_link,
        )
        raise HTTPException(
            status_code=504,
            detail={
                "message": "Не удалось обновить бронь в Telegram. Попробуйте позже.",
                "error_id": error_id,
                "error_detail": str(exc),
                "post_link": post_link,
            },
        )
    except BadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            error_id = uuid.uuid4().hex[:8]
            post_link = get_private_channel_post_link(private_channel_id, message_ids[0])
            logger.exception("ann:reserve telegram_bad_request ann_id=%s user_id=%s error=%s", ann_id, user_id, exc)
            await send_bug_report(
                action="reserve_ad",
                user=user,
                ann_id=ann_id,
                status="error",
                error_id=error_id,
                message="Telegram reservation update failed.",
                detail=str(exc),
                post_link=post_link,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Не удалось обновить бронь в Telegram. Возможно, Telegram уже не разрешает редактировать этот пост.",
                    "error_id": error_id,
                    "error_detail": str(exc),
                    "post_link": post_link,
                },
            )
        logger.warning("ann:reserve message already matches state ann_id=%s user_id=%s", ann_id, user_id)
    except TelegramError as exc:
        error_id = uuid.uuid4().hex[:8]
        post_link = get_private_channel_post_link(private_channel_id, message_ids[0])
        logger.exception("ann:reserve telegram_error ann_id=%s user_id=%s error=%s", ann_id, user_id, exc)
        await send_bug_report(
            action="reserve_ad",
            user=user,
            ann_id=ann_id,
            status="error",
            error_id=error_id,
            message="Telegram reservation update failed.",
            detail=str(exc),
            post_link=post_link,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Не удалось обновить бронь в Telegram.",
                "error_id": error_id,
                "error_detail": str(exc),
                "post_link": post_link,
            },
        )

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE announcements SET is_reserved = ?, updated_at = ? WHERE id = ?",
            (1 if new_is_reserved else 0, get_serbia_time(), ann_id),
        )
        await db.commit()

    return {
        "post_link": get_private_channel_post_link(private_channel_id, message_ids[0]),
        "is_reserved": new_is_reserved,
    }


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
