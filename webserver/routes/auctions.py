import json
import mimetypes
from datetime import datetime, timedelta
from typing import Any, Dict

import aiosqlite
import pytz
from fastapi import APIRouter, Depends, HTTPException, Response
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.error import BadRequest, NetworkError, TelegramError, TimedOut

from config import DB_PATH, PRIVATE_CHANNEL_ID
from utils import get_private_channel_post_link, get_serbia_time
from webserver.auth import get_user_from_request
from webserver.models import AnnouncementIn, BidIn
from webserver.settings import WEBAPP_URL, logger
from webserver.telegram_client import bot, format_auction_text, make_bid_link_md, normalize_chat_id, texts_for

# An auction may last at most 2 days minus 10 minutes (mirror of announcements).
MAX_AUCTION_DURATION = timedelta(days=2) - timedelta(minutes=10)

router = APIRouter()


def _get_serbia_now_str() -> str:
    belgrade_tz = pytz.timezone("Europe/Belgrade")
    return datetime.now(pytz.utc).astimezone(belgrade_tz).strftime("%Y-%m-%d %H:%M:%S")


@router.get("/api/auctions/{ann_id}")
async def get_auction(ann_id: int) -> Dict[str, Any]:
    logger.info("auction:get ann_id=%s", ann_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, description, start_price, current_price, min_step, auction_end_at,
                   auction_status, winner_username, username, photo_file_ids, message_ids,
                   (SELECT COUNT(*) FROM auction_bids WHERE announcement_id = announcements.id) as bids_count
            FROM announcements
            WHERE id = ? AND COALESCE(ad_type,'fixed') = 'auction'
            """,
            (ann_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Auction not found")

    (
        aid,
        description,
        start_price,
        current_price,
        min_step,
        auction_end_at,
        auction_status,
        winner_username,
        seller_username,
        photo_file_ids,
        message_ids_json,
        bids_count,
    ) = row

    message_ids = json.loads(message_ids_json) if message_ids_json else []
    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
    post_link = (
        get_private_channel_post_link(private_channel_id, message_ids[0])
        if message_ids and private_channel_id is not None
        else None
    )

    return {
        "id": aid,
        "description": description,
        "start_price": start_price,
        "current_price": current_price,
        "min_step": min_step,
        "auction_end_at": auction_end_at,
        "auction_status": auction_status,
        "winner_username": winner_username,
        "bids_count": bids_count or 0,
        "seller_username": seller_username,
        "photo_file_ids": json.loads(photo_file_ids) if photo_file_ids else [],
        "post_link": post_link,
    }


@router.get("/api/auctions/{ann_id}/photo")
async def get_auction_photo(
    ann_id: int,
    file_id: str,
    user: Dict[str, Any] = Depends(get_user_from_request),
) -> Response:
    """Serve an auction photo to any authenticated user (not only the owner),
    so bidders can see all photos on the bid screen. Scoped to the auction's
    own photo_file_ids to prevent fetching arbitrary files."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT photo_file_ids FROM announcements WHERE id = ? AND COALESCE(ad_type,'fixed') = 'auction'",
            (ann_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Auction not found")

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


@router.post("/api/auctions/{ann_id}/bid")
async def place_bid(
    ann_id: int, payload: BidIn, user: Dict[str, Any] = Depends(get_user_from_request)
) -> Dict[str, Any]:
    user_id = user.get("id")
    username = user.get("username") or "None"
    display_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])).strip() or None
    winner_name = f"@{username}" if username != "None" else (display_name or str(user_id))
    logger.info("auction:bid ann_id=%s user_id=%s amount=%s", ann_id, user_id, payload.amount)

    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
    if private_channel_id is None:
        raise HTTPException(status_code=500, detail="PRIVATE_CHANNEL_ID is not set")

    # isolation_level=None → no implicit BEGIN, so the explicit BEGIN IMMEDIATE
    # below gives us full control over the transaction.
    async with aiosqlite.connect(DB_PATH, timeout=15, isolation_level=None) as db:
        # Take the write lock up front so the read-validate-write below is atomic:
        # two concurrent bids can't both pass against the same current_price.
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """
            SELECT id, user_id, description, username, contact_info, start_price, current_price, min_step,
                   auction_end_at, auction_status, message_ids, photo_file_ids, owner_language_code,
                   winner_user_id, winner_language_code
            FROM announcements
            WHERE id = ? AND COALESCE(ad_type,'fixed') = 'auction'
            """,
            (ann_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail={"code": "auction_not_found", "message": "Auction not found"})

        (
            aid,
            seller_user_id,
            description,
            seller_username,
            contact_info,
            start_price,
            current_price,
            min_step,
            auction_end_at,
            auction_status,
            message_ids_json,
            photo_file_ids,
            owner_language_code,
            prev_winner_user_id,
            prev_winner_language_code,
        ) = row

        # Validations
        if auction_status != "active":
            raise HTTPException(status_code=400, detail={"code": "auction_not_active", "message": "Auction is not active"})

        now_str = _get_serbia_now_str()
        if auction_end_at and auction_end_at <= now_str:
            raise HTTPException(status_code=400, detail={"code": "auction_ended", "message": "Auction has already ended"})

        if user_id == seller_user_id:
            raise HTTPException(status_code=403, detail={"code": "own_auction", "message": "You cannot bid on your own auction"})

        if current_price is None:
            # No bids yet — first bid must be at least start_price + step.
            min_required = (start_price if start_price is not None else 0) + (min_step or 0)
        else:
            min_required = current_price + (min_step or 1)
        if payload.amount < min_required:
            raise HTTPException(
                status_code=422,
                detail={"code": "bid_too_low", "min_required": min_required, "message": f"Bid must be at least {min_required}"},
            )

        # Insert bid
        await db.execute(
            "INSERT INTO auction_bids (announcement_id, user_id, username, amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (ann_id, user_id, winner_name, payload.amount, now_str),
        )

        # Update announcement
        await db.execute(
            "UPDATE announcements SET current_price = ?, winner_user_id = ?, winner_username = ?, winner_language_code = ? WHERE id = ?",
            (payload.amount, user_id, winner_name, user.get("language_code"), ann_id),
        )
        await db.commit()

        # Fetch updated bids count
        cursor2 = await db.execute(
            "SELECT COUNT(*) FROM auction_bids WHERE announcement_id = ?", (ann_id,)
        )
        bids_count_row = await cursor2.fetchone()
        bids_count = bids_count_row[0] if bids_count_row else 1

    # Edit channel post. For an album the caption lives on the first message;
    # for a text-only auction it's the only message — message_ids[0] covers both.
    message_ids = json.loads(message_ids_json) if message_ids_json else []
    has_photo = bool(json.loads(photo_file_ids)) if photo_file_ids else False
    if message_ids:
        post_message_id = message_ids[0]
        updated_text = format_auction_text(
            description=description,
            username=seller_username,
            contact_info=contact_info,
            user_display=None,
            start_price=start_price,
            current_price=payload.amount,
            min_step=min_step,
            auction_end_at=auction_end_at,
            winner_username=winner_name,
            auction_status="active",
            language_code=owner_language_code,
        )
        updated_text = updated_text + "\n\n" + make_bid_link_md(ann_id, owner_language_code)
        try:
            if has_photo:
                # Album caption — edit the caption of the first photo.
                await bot.edit_message_caption(
                    chat_id=private_channel_id,
                    message_id=post_message_id,
                    caption=updated_text,
                    parse_mode="MarkdownV2",
                )
            else:
                await bot.edit_message_text(
                    chat_id=private_channel_id,
                    message_id=post_message_id,
                    text=updated_text,
                    parse_mode="MarkdownV2",
                )
        except TelegramError as exc:
            logger.warning(
                "auction:bid edit_message failed ann_id=%s message_id=%s error=%s",
                ann_id,
                post_message_id,
                exc,
            )

    # Notify the auction owner about the new bid, with a button that opens the
    # Mini App on the bids screen for this announcement.
    try:
        owner_texts = texts_for(owner_language_code)
        desc_preview = (description or "").strip()
        if len(desc_preview) > 120:
            desc_preview = desc_preview[:120].rstrip() + "…"
        notify_text = (
            f"{owner_texts.AUCTION_NEW_BID_TITLE}\n\n"
            f"{desc_preview}\n\n"
            f"{owner_texts.AUCTION_NEW_BID_AMOUNT}: {payload.amount}\n"
            f"{owner_texts.AUCTION_NEW_BID_FROM}: {winner_name}\n"
            f"{owner_texts.AUCTION_NEW_BID_TOTAL}: {bids_count}"
        )
        bids_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(owner_texts.AUCTION_VIEW_BIDS_BUTTON, web_app=WebAppInfo(f"{WEBAPP_URL}?bids={ann_id}"))]]
        )
        await bot.send_message(chat_id=seller_user_id, text=notify_text, reply_markup=bids_keyboard)
    except Exception as exc:
        logger.warning("auction:bid seller_notify failed ann_id=%s user_id=%s error=%s", ann_id, seller_user_id, exc)

    # Notify the previous top bidder that they've been outbid, with a link to the
    # post and a button to place a new bid.
    if prev_winner_user_id and prev_winner_user_id != user_id:
        try:
            outbid_texts = texts_for(prev_winner_language_code)
            post_link = (
                get_private_channel_post_link(private_channel_id, message_ids[0])
                if message_ids and private_channel_id is not None
                else ""
            )
            desc_preview = (description or "").strip()
            if len(desc_preview) > 120:
                desc_preview = desc_preview[:120].rstrip() + "…"
            outbid_text = outbid_texts.AUCTION_OUTBID_MESSAGE.format(
                desc=desc_preview, amount=payload.amount, link=post_link
            )
            outbid_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(outbid_texts.AUCTION_OUTBID_BUTTON, web_app=WebAppInfo(f"{WEBAPP_URL}?bid={ann_id}"))]]
            )
            await bot.send_message(chat_id=prev_winner_user_id, text=outbid_text, reply_markup=outbid_keyboard)
        except Exception as exc:
            logger.warning("auction:bid outbid_notify failed ann_id=%s user_id=%s error=%s", ann_id, prev_winner_user_id, exc)

    return {"ok": True, "current_price": payload.amount}


@router.get("/api/auctions/{ann_id}/bids")
async def list_bids(
    ann_id: int, user: Dict[str, Any] = Depends(get_user_from_request)
) -> Dict[str, Any]:
    """Return all bids for an auction. Restricted to the auction owner."""
    user_id = user.get("id")
    logger.info("auction:bids ann_id=%s user_id=%s", ann_id, user_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id, description, start_price, current_price, min_step,
                   auction_end_at, auction_status
            FROM announcements
            WHERE id = ? AND COALESCE(ad_type,'fixed') = 'auction'
            """,
            (ann_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Auction not found")

        (
            seller_user_id,
            description,
            start_price,
            current_price,
            min_step,
            auction_end_at,
            auction_status,
        ) = row

        if user_id != seller_user_id:
            raise HTTPException(status_code=403, detail="Only the owner can view bids")

        cursor2 = await db.execute(
            """
            SELECT username, amount, created_at
            FROM auction_bids
            WHERE announcement_id = ?
            ORDER BY amount DESC, created_at DESC
            """,
            (ann_id,),
        )
        bid_rows = await cursor2.fetchall()

    bids = [
        {"username": b[0], "amount": b[1], "created_at": b[2]}
        for b in bid_rows
    ]

    return {
        "id": ann_id,
        "description": description,
        "start_price": start_price,
        "current_price": current_price,
        "min_step": min_step,
        "auction_end_at": auction_end_at,
        "auction_status": auction_status,
        "bids": bids,
    }


async def finish_auction(ann_id: int, expected_user_id: int = None) -> Dict[str, Any]:
    """Finish a single auction: mark it finished, edit the channel post to the
    finished state and notify the seller and winner. Shared by the manual
    "stop" endpoint and the auto-finish background job.

    If expected_user_id is given (manual stop), ownership and active-state are
    enforced with HTTP errors; otherwise (the job) a non-active auction is
    silently skipped.
    """
    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id, description, username, contact_info, start_price, current_price,
                   min_step, auction_end_at, winner_user_id, winner_username, message_ids,
                   photo_file_ids, owner_language_code, winner_language_code, auction_status
            FROM announcements
            WHERE id = ? AND COALESCE(ad_type,'fixed') = 'auction'
            """,
            (ann_id,),
        )
        row = await cursor.fetchone()

        if not row:
            if expected_user_id is not None:
                raise HTTPException(status_code=404, detail="Auction not found")
            return {"ok": False, "reason": "not_found"}

        (
            seller_user_id,
            description,
            seller_username,
            contact_info,
            start_price,
            current_price,
            min_step,
            auction_end_at,
            winner_user_id,
            winner_username,
            message_ids_json,
            photo_file_ids,
            owner_language_code,
            winner_language_code,
            auction_status,
        ) = row

        if expected_user_id is not None and seller_user_id != expected_user_id:
            raise HTTPException(status_code=403, detail="Only the owner can stop the auction")

        if auction_status != "active":
            if expected_user_id is not None:
                raise HTTPException(status_code=400, detail="Auction is not active")
            return {"ok": False, "reason": "not_active"}

        await db.execute(
            "UPDATE announcements SET auction_status = 'finished' WHERE id = ?",
            (ann_id,),
        )
        await db.commit()

    logger.info("auction:finish ann_id=%s winner_user_id=%s manual=%s", ann_id, winner_user_id, expected_user_id is not None)

    message_ids = json.loads(message_ids_json) if message_ids_json else []
    has_photo = bool(json.loads(photo_file_ids)) if photo_file_ids else False

    # Edit the channel post to the finished state.
    if message_ids and private_channel_id is not None:
        post_message_id = message_ids[0]
        finished_text = format_auction_text(
            description=description,
            username=seller_username,
            contact_info=contact_info,
            user_display=None,
            start_price=start_price,
            current_price=current_price,
            min_step=min_step,
            auction_end_at=auction_end_at,
            winner_username=winner_username,
            auction_status="finished",
            language_code=owner_language_code,
        )
        try:
            if has_photo:
                await bot.edit_message_caption(
                    chat_id=private_channel_id, message_id=post_message_id,
                    caption=finished_text, parse_mode="MarkdownV2", reply_markup=None,
                )
            else:
                await bot.edit_message_text(
                    chat_id=private_channel_id, message_id=post_message_id,
                    text=finished_text, parse_mode="MarkdownV2", reply_markup=None,
                )
        except Exception as exc:
            logger.warning("auction:finish edit_message failed ann_id=%s error=%s", ann_id, exc)

    post_link = (
        get_private_channel_post_link(private_channel_id, message_ids[0])
        if message_ids and private_channel_id is not None
        else ""
    )
    if seller_username and seller_username != "None":
        seller_contact = f"@{seller_username}"
    else:
        seller_contact = (contact_info or "").strip() or "—"

    # Notify seller (in the owner's language).
    try:
        seller_texts = texts_for(owner_language_code)
        if winner_username:
            seller_msg = seller_texts.AUCTION_SELLER_FINISHED_WIN.format(
                winner=winner_username, price=current_price, link=post_link
            )
        else:
            seller_msg = seller_texts.AUCTION_SELLER_FINISHED_NOBIDS.format(link=post_link)
        await bot.send_message(chat_id=seller_user_id, text=seller_msg)
    except Exception as exc:
        logger.warning("auction:finish seller_notify failed ann_id=%s user_id=%s error=%s", ann_id, seller_user_id, exc)

    # Notify winner (in the winner's language).
    if winner_user_id:
        try:
            winner_texts = texts_for(winner_language_code)
            winner_msg = winner_texts.AUCTION_WINNER_FINISHED.format(
                price=current_price, seller_contact=seller_contact, link=post_link
            )
            await bot.send_message(chat_id=winner_user_id, text=winner_msg)
        except Exception as exc:
            logger.warning("auction:finish winner_notify failed ann_id=%s user_id=%s error=%s", ann_id, winner_user_id, exc)

    return {"ok": True}


@router.post("/api/auctions/{ann_id}/stop")
async def stop_auction(
    ann_id: int, user: Dict[str, Any] = Depends(get_user_from_request)
) -> Dict[str, Any]:
    """Let the owner finish their auction early."""
    user_id = user.get("id")
    logger.info("auction:stop ann_id=%s user_id=%s", ann_id, user_id)
    return await finish_auction(ann_id, expected_user_id=user_id)


@router.post("/api/auctions/{ann_id}/edit")
async def edit_auction(
    ann_id: int, payload: AnnouncementIn, user: Dict[str, Any] = Depends(get_user_from_request)
) -> Dict[str, Any]:
    """Edit a running auction IN PLACE (no repost): update the DB and edit the
    existing channel post's caption. Used when photos didn't change — albums
    can't be restructured in place, so photo changes go through republish.
    Start price and existing bids are preserved."""
    user_id = user.get("id")
    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id, username, contact_info, message_ids, photo_file_ids, start_price,
                   current_price, winner_username, owner_language_code, auction_status
            FROM announcements
            WHERE id = ? AND COALESCE(ad_type,'fixed') = 'auction'
            """,
            (ann_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Auction not found")
        (
            seller_user_id,
            seller_username,
            _old_contact,
            message_ids_json,
            photo_file_ids,
            start_price,
            current_price,
            winner_username,
            owner_language_code,
            auction_status,
        ) = row

        if user_id != seller_user_id:
            raise HTTPException(status_code=403, detail="Only the owner can edit the auction")
        message_ids = json.loads(message_ids_json) if message_ids_json else []
        if not message_ids:
            raise HTTPException(status_code=400, detail="Auction is not published")
        if auction_status != "active":
            raise HTTPException(status_code=400, detail="Auction is not active")

        contact_info = (payload.contact_info or "").strip()
        new_min_step = payload.min_step if payload.min_step else None

        # New end time = now + chosen duration (capped). Keep current if not given.
        new_end_at = None
        if payload.auction_duration_hours:
            belgrade_tz = pytz.timezone("Europe/Belgrade")
            now = datetime.now(pytz.utc).astimezone(belgrade_tz)
            end_dt = min(now + timedelta(hours=payload.auction_duration_hours), now + MAX_AUCTION_DURATION)
            new_end_at = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        await db.execute(
            """
            UPDATE announcements
            SET description = ?, contact_info = ?, photo_file_ids = ?, updated_at = ?,
                min_step = COALESCE(?, min_step),
                auction_duration_hours = COALESCE(?, auction_duration_hours),
                auction_end_at = COALESCE(?, auction_end_at)
            WHERE id = ?
            """,
            (
                payload.description,
                contact_info,
                json.dumps(payload.photo_file_ids),
                get_serbia_time(),
                new_min_step,
                payload.auction_duration_hours,
                new_end_at,
                ann_id,
            ),
        )
        await db.commit()

        # Re-read the effective values for rendering.
        cursor2 = await db.execute(
            "SELECT min_step, auction_end_at FROM announcements WHERE id = ?", (ann_id,)
        )
        eff_min_step, eff_end_at = await cursor2.fetchone()

    # Rebuild and edit the post caption/text in place.
    has_photo = bool(json.loads(photo_file_ids)) if photo_file_ids else False
    message = format_auction_text(
        description=payload.description,
        username=seller_username,
        contact_info=contact_info,
        user_display=None,
        start_price=start_price,
        current_price=current_price,
        min_step=eff_min_step,
        auction_end_at=eff_end_at,
        winner_username=winner_username,
        auction_status="active",
        language_code=owner_language_code,
    )
    message = message + "\n\n" + make_bid_link_md(ann_id, owner_language_code)

    if private_channel_id is not None:
        post_message_id = message_ids[0]
        try:
            if has_photo:
                await bot.edit_message_caption(
                    chat_id=private_channel_id, message_id=post_message_id,
                    caption=message, parse_mode="MarkdownV2",
                )
            else:
                await bot.edit_message_text(
                    chat_id=private_channel_id, message_id=post_message_id,
                    text=message, parse_mode="MarkdownV2",
                )
        except TelegramError as exc:
            logger.warning("auction:edit edit_message failed ann_id=%s error=%s", ann_id, exc)
            raise HTTPException(status_code=502, detail=f"Failed to edit post: {exc}")

    post_link = (
        get_private_channel_post_link(private_channel_id, message_ids[0])
        if private_channel_id is not None
        else None
    )
    return {"ok": True, "post_link": post_link}
