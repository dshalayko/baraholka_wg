import json
from datetime import datetime, timedelta
from typing import Any, Dict

import aiosqlite
import pytz
from fastapi import APIRouter, Depends, HTTPException, Response
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.error import BadRequest, TelegramError

from config import DB_PATH, PRIVATE_CHANNEL_ID
from utils import get_private_channel_post_link, get_serbia_time
from webserver.auth import get_user_from_request
from webserver.models import AnnouncementIn, BidIn
from webserver.photos import serve_telegram_photo
from webserver.settings import WEBAPP_URL, logger
from webserver.telegram_client import bot, format_auction_text, make_bid_link_md, normalize_chat_id, normalize_currency, texts_for

# An auction may last at most 2 days minus 10 minutes (mirror of announcements).
MAX_AUCTION_DURATION = timedelta(days=2) - timedelta(minutes=10)

# Anti-sniping ("антиснайпер"): a bid placed inside this window before the end
# pushes the end out to now + the same window, so there is always this much time
# left for others to answer the last bid. Bids outside the window change nothing.
ANTISNIPE_WINDOW = timedelta(minutes=10)

STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

router = APIRouter()


def _get_serbia_now_str() -> str:
    belgrade_tz = pytz.timezone("Europe/Belgrade")
    return datetime.now(pytz.utc).astimezone(belgrade_tz).strftime(STAMP_FORMAT)


def _antisnipe_end_at(auction_end_at, now_str: str):
    """Return the extended end stamp if this bid falls inside the anti-snipe
    window, or None when no extension is due (bid too early, or no end time).

    Both stamps are Belgrade-local strings in STAMP_FORMAT, so they can be
    compared as naive datetimes.
    """
    if not auction_end_at:
        return None
    try:
        end_dt = datetime.strptime(auction_end_at, STAMP_FORMAT)
        now_dt = datetime.strptime(now_str, STAMP_FORMAT)
    except (TypeError, ValueError):
        logger.warning("auction:antisnipe unparsable end_at=%r", auction_end_at)
        return None
    if end_dt - now_dt > ANTISNIPE_WINDOW:
        return None
    return (now_dt + ANTISNIPE_WINDOW).strftime(STAMP_FORMAT)


@router.get("/api/auctions/{ann_id}")
async def get_auction(ann_id: int, user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    logger.info("auction:get ann_id=%s user_id=%s", ann_id, user.get("id"))
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, description, start_price, current_price, min_step, buyout_price, auction_end_at,
                   auction_status, winner_username, username, photo_file_ids, message_ids, currency,
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
        buyout_price,
        auction_end_at,
        auction_status,
        winner_username,
        seller_username,
        photo_file_ids,
        message_ids_json,
        currency,
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
        "buyout_price": buyout_price,
        "auction_end_at": auction_end_at,
        "auction_status": auction_status,
        "winner_username": winner_username,
        "bids_count": bids_count or 0,
        "seller_username": seller_username,
        "photo_file_ids": json.loads(photo_file_ids) if photo_file_ids else [],
        "post_link": post_link,
        "currency": currency or "RSD",
        # Lets the bid screen spell out the anti-snipe rule without hardcoding it.
        "antisnipe_minutes": int(ANTISNIPE_WINDOW.total_seconds() // 60),
    }


@router.get("/api/auctions/{ann_id}/photo")
async def get_auction_photo(
    ann_id: int,
    file_id: str,
    size: str = "full",
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

    return await serve_telegram_photo(file_id, size)


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
                   buyout_price, auction_end_at, auction_status, message_ids, photo_file_ids, owner_language_code,
                   winner_user_id, winner_language_code, currency
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
            buyout_price,
            auction_end_at,
            auction_status,
            message_ids_json,
            photo_file_ids,
            owner_language_code,
            prev_winner_user_id,
            prev_winner_language_code,
            currency,
        ) = row
        currency = normalize_currency(currency)

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

        # A bid at or above the buyout price ends the auction outright, so there is
        # nothing to protect from sniping — skip the extension in that case.
        wins_by_buyout = buyout_price is not None and payload.amount >= buyout_price
        new_end_at = None if wins_by_buyout else _antisnipe_end_at(auction_end_at, now_str)

        # Insert bid
        await db.execute(
            "INSERT INTO auction_bids (announcement_id, user_id, username, amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (ann_id, user_id, winner_name, payload.amount, now_str),
        )

        # Update announcement. The anti-snipe extension is written under the same
        # lock as the bid, so the auto-finish job can never see a stale end time.
        await db.execute(
            """
            UPDATE announcements
            SET current_price = ?, winner_user_id = ?, winner_username = ?, winner_language_code = ?,
                auction_end_at = COALESCE(?, auction_end_at)
            WHERE id = ?
            """,
            (payload.amount, user_id, winner_name, user.get("language_code"), new_end_at, ann_id),
        )
        await db.commit()

        if new_end_at:
            logger.info(
                "auction:bid antisnipe extended ann_id=%s old_end=%s new_end=%s",
                ann_id, auction_end_at, new_end_at,
            )
            auction_end_at = new_end_at

        # Fetch updated bids count
        cursor2 = await db.execute(
            "SELECT COUNT(*) FROM auction_bids WHERE announcement_id = ?", (ann_id,)
        )
        bids_count_row = await cursor2.fetchone()
        bids_count = bids_count_row[0] if bids_count_row else 1

    # A bid at or above the buyout price wins instantly: finish_auction rewrites
    # the post to the finished state and notifies the seller and the winner, so
    # the regular post-edit and notifications below are skipped.
    if wins_by_buyout:
        await finish_auction(ann_id)
        return {"ok": True, "current_price": payload.amount, "won": True}

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
            currency=currency,
            buyout_price=buyout_price,
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
            f"{owner_texts.AUCTION_NEW_BID_AMOUNT}: {payload.amount} {currency}\n"
            f"{owner_texts.AUCTION_NEW_BID_FROM}: {winner_name}\n"
            f"{owner_texts.AUCTION_NEW_BID_TOTAL}: {bids_count}"
        )
        if new_end_at:
            notify_text += "\n" + owner_texts.AUCTION_EXTENDED_NOTE.format(
                minutes=int(ANTISNIPE_WINDOW.total_seconds() // 60), until=new_end_at
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
                desc=desc_preview, amount=f"{payload.amount} {currency}", link=post_link
            )
            # The extension is the whole point of the anti-sniper for this user:
            # tell them how long they still have to answer.
            if new_end_at:
                outbid_text += "\n" + outbid_texts.AUCTION_EXTENDED_NOTE.format(
                    minutes=int(ANTISNIPE_WINDOW.total_seconds() // 60), until=new_end_at
                )
            outbid_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(outbid_texts.AUCTION_OUTBID_BUTTON, web_app=WebAppInfo(f"{WEBAPP_URL}?bid={ann_id}"))]]
            )
            await bot.send_message(chat_id=prev_winner_user_id, text=outbid_text, reply_markup=outbid_keyboard)
        except Exception as exc:
            logger.warning("auction:bid outbid_notify failed ann_id=%s user_id=%s error=%s", ann_id, prev_winner_user_id, exc)

    return {
        "ok": True,
        "current_price": payload.amount,
        "auction_end_at": auction_end_at,
        "extended": bool(new_end_at),
    }


@router.post("/api/auctions/{ann_id}/buyout")
async def buyout_auction(
    ann_id: int, user: Dict[str, Any] = Depends(get_user_from_request)
) -> Dict[str, Any]:
    """Instantly win the auction at the seller's buyout price: the buyout is
    recorded as a regular bid and the auction is finished on the spot."""
    user_id = user.get("id")
    username = user.get("username") or "None"
    display_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])).strip() or None
    winner_name = f"@{username}" if username != "None" else (display_name or str(user_id))
    logger.info("auction:buyout ann_id=%s user_id=%s", ann_id, user_id)

    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
    if private_channel_id is None:
        raise HTTPException(status_code=500, detail="PRIVATE_CHANNEL_ID is not set")

    # Same locking pattern as place_bid: BEGIN IMMEDIATE serializes concurrent
    # buyers so only the first one becomes the recorded winner.
    async with aiosqlite.connect(DB_PATH, timeout=15, isolation_level=None) as db:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """
            SELECT user_id, buyout_price, auction_end_at, auction_status
            FROM announcements
            WHERE id = ? AND COALESCE(ad_type,'fixed') = 'auction'
            """,
            (ann_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail={"code": "auction_not_found", "message": "Auction not found"})

        seller_user_id, buyout_price, auction_end_at, auction_status = row

        if auction_status != "active":
            raise HTTPException(status_code=400, detail={"code": "auction_not_active", "message": "Auction is not active"})

        now_str = _get_serbia_now_str()
        if auction_end_at and auction_end_at <= now_str:
            raise HTTPException(status_code=400, detail={"code": "auction_ended", "message": "Auction has already ended"})

        if user_id == seller_user_id:
            raise HTTPException(status_code=403, detail={"code": "own_auction", "message": "You cannot buy your own auction"})

        if not buyout_price:
            raise HTTPException(status_code=400, detail={"code": "no_buyout", "message": "This auction has no buyout price"})

        await db.execute(
            "INSERT INTO auction_bids (announcement_id, user_id, username, amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (ann_id, user_id, winner_name, buyout_price, now_str),
        )
        await db.execute(
            "UPDATE announcements SET current_price = ?, winner_user_id = ?, winner_username = ?, winner_language_code = ? WHERE id = ?",
            (buyout_price, user_id, winner_name, user.get("language_code"), ann_id),
        )
        await db.commit()

    # finish_auction edits the channel post to the finished state and notifies
    # the seller and the winner.
    await finish_auction(ann_id)
    return {"ok": True, "current_price": buyout_price, "won": True}


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
                   auction_end_at, auction_status, currency
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
            currency,
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
        "currency": currency or "RSD",
        "bids": bids,
    }


async def finish_auction(
    ann_id: int, expected_user_id: int = None, require_expired: bool = False
) -> Dict[str, Any]:
    """Finish a single auction: mark it finished, edit the channel post to the
    finished state and notify the seller and winner. Shared by the manual
    "stop" endpoint and the auto-finish background job.

    If expected_user_id is given (manual stop), ownership and active-state are
    enforced with HTTP errors; otherwise (the job) a non-active auction is
    silently skipped.

    require_expired is for the auto-finish job: it re-checks the end time under
    the write lock, so an anti-snipe extension that landed after the job picked
    this auction up keeps the auction alive instead of being finished anyway.
    The buyout path deliberately leaves it False — that auction ends early.
    """
    private_channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)

    # Same locking pattern as place_bid: the read-check-write below must not
    # interleave with a bid that extends the auction.
    async with aiosqlite.connect(DB_PATH, timeout=15, isolation_level=None) as db:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """
            SELECT user_id, description, username, contact_info, start_price, current_price,
                   min_step, auction_end_at, winner_user_id, winner_username, message_ids,
                   photo_file_ids, owner_language_code, winner_language_code, auction_status, currency
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
            currency,
        ) = row
        currency = normalize_currency(currency)

        if expected_user_id is not None and seller_user_id != expected_user_id:
            raise HTTPException(status_code=403, detail="Only the owner can stop the auction")

        if auction_status != "active":
            if expected_user_id is not None:
                raise HTTPException(status_code=400, detail="Auction is not active")
            return {"ok": False, "reason": "not_active"}

        # A bid extended the auction after the job listed it as expired.
        if require_expired and auction_end_at and auction_end_at > _get_serbia_now_str():
            logger.info("auction:finish skipped, extended ann_id=%s end_at=%s", ann_id, auction_end_at)
            return {"ok": False, "reason": "extended"}

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
            currency=currency,
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
                winner=winner_username, price=f"{current_price} {currency}", link=post_link
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
                price=f"{current_price} {currency}", seller_contact=seller_contact, link=post_link
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
                   current_price, winner_username, owner_language_code, auction_status, currency
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
            currency,
        ) = row
        currency = normalize_currency(currency)

        if user_id != seller_user_id:
            raise HTTPException(status_code=403, detail="Only the owner can edit the auction")
        message_ids = json.loads(message_ids_json) if message_ids_json else []
        if not message_ids:
            raise HTTPException(status_code=400, detail="Auction is not published")
        if auction_status != "active":
            raise HTTPException(status_code=400, detail="Auction is not active")

        contact_info = (payload.contact_info or "").strip()
        new_min_step = payload.min_step if payload.min_step else None
        new_buyout_price = payload.buyout_price if payload.buyout_price else None
        new_currency = normalize_currency(payload.currency) if payload.currency else None

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
                buyout_price = COALESCE(?, buyout_price),
                auction_duration_hours = COALESCE(?, auction_duration_hours),
                auction_end_at = COALESCE(?, auction_end_at),
                currency = COALESCE(?, currency)
            WHERE id = ?
            """,
            (
                payload.description,
                contact_info,
                json.dumps(payload.photo_file_ids),
                get_serbia_time(),
                new_min_step,
                new_buyout_price,
                payload.auction_duration_hours,
                new_end_at,
                new_currency,
                ann_id,
            ),
        )
        await db.commit()

        # Re-read the effective values for rendering.
        cursor2 = await db.execute(
            "SELECT min_step, buyout_price, auction_end_at, currency FROM announcements WHERE id = ?", (ann_id,)
        )
        eff_min_step, eff_buyout_price, eff_end_at, eff_currency = await cursor2.fetchone()

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
        currency=eff_currency,
        buyout_price=eff_buyout_price,
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
        except BadRequest as exc:
            # Nothing actually changed in the post — that's fine, the DB is updated.
            if "not modified" in str(exc).lower():
                logger.info("auction:edit post unchanged ann_id=%s", ann_id)
            else:
                logger.warning("auction:edit edit_message failed ann_id=%s error=%s", ann_id, exc)
                raise HTTPException(status_code=502, detail=f"Failed to edit post: {exc}")
        except TelegramError as exc:
            logger.warning("auction:edit edit_message failed ann_id=%s error=%s", ann_id, exc)
            raise HTTPException(status_code=502, detail=f"Failed to edit post: {exc}")

    post_link = (
        get_private_channel_post_link(private_channel_id, message_ids[0])
        if private_channel_id is not None
        else None
    )
    return {"ok": True, "post_link": post_link}
