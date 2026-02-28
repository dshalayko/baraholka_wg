import json
from datetime import timedelta
from typing import Any, Dict

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from telegram.error import TelegramError

from config import DB_PATH, DSHALAYKO_ID, PRIVATE_CHANNEL_ID, SLONSKI_ID
from utils import get_private_channel_post_link, get_serbia_time, parse_timestamp
from webserver.auth import get_user_from_request
from webserver.telegram_client import bot, normalize_chat_id

router = APIRouter()

ALLOWED_EVENTS = {"app_open", "open_comments", "api_errors"}
SUMMARY_KEYS = ["app_open", "publish_success", "publish_fail", "open_comments", "api_errors"]


async def increment_stat(stat_key: str, amount: int = 1) -> None:
    if not stat_key or amount <= 0:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO app_stats (stat_key, stat_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(stat_key) DO UPDATE SET
                stat_value = stat_value + excluded.stat_value,
                updated_at = excluded.updated_at
            """,
            (stat_key, amount, get_serbia_time()),
        )
        await db.commit()


async def get_stats(keys: list[str]) -> dict[str, int]:
    if not keys:
        return {}
    placeholders = ",".join("?" for _ in keys)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"SELECT stat_key, stat_value FROM app_stats WHERE stat_key IN ({placeholders})",
            keys,
        )
        rows = await cursor.fetchall()
    data = {key: 0 for key in keys}
    for stat_key, stat_value in rows:
        data[stat_key] = int(stat_value or 0)
    return data


def _admin_ids() -> set[int]:
    ids = set()
    for raw in (SLONSKI_ID, DSHALAYKO_ID):
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            ids.add(value)
    return ids


async def _is_channel_admin(user_id: int) -> bool:
    chat_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
    if chat_id is None:
        return False
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except TelegramError:
        return False
    status = getattr(member, "status", "")
    return status in {"administrator", "creator"}


async def _ensure_admin(user: Dict[str, Any]) -> None:
    user_id = user.get("id")
    if await _is_channel_admin(user_id):
        return
    if user_id in _admin_ids():
        return
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/api/stats/event")
async def track_event(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    _ = user
    event_name = str(payload.get("event") or "").strip()
    if event_name not in ALLOWED_EVENTS:
        raise HTTPException(status_code=400, detail="Unsupported event")
    await increment_stat(event_name)
    return {"status": "ok"}


@router.get("/api/stats/summary")
async def stats_summary(user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    await _ensure_admin(user)
    counters = await get_stats(SUMMARY_KEYS)

    async with aiosqlite.connect(DB_PATH) as db:
        total_ads_cursor = await db.execute("SELECT COUNT(*) FROM announcements")
        total_ads = int((await total_ads_cursor.fetchone())[0] or 0)
        published_ads_cursor = await db.execute("SELECT COUNT(*) FROM announcements WHERE message_ids IS NOT NULL AND message_ids != '[]'")
        published_ads = int((await published_ads_cursor.fetchone())[0] or 0)
        list_cursor = await db.execute(
            """
            SELECT id, user_id, username, description, message_ids, last_published_is_edit, timestamp
            FROM announcements
            ORDER BY id DESC
            """
        )
        rows = await list_cursor.fetchall()

    ads = []
    for row in rows:
        ann_id, user_id, username, description, message_ids_raw, last_published_is_edit, timestamp = row
        is_published = bool(message_ids_raw and message_ids_raw != "[]")
        if not is_published:
            status = "draft"
        elif bool(last_published_is_edit):
            status = "updated"
        else:
            status = "published"
        ads.append(
            {
                "id": ann_id,
                "user_id": user_id,
                "username": username or "",
                "description": description or "",
                "status": status,
                "timestamp": timestamp,
            }
        )

    return {
        "is_admin": True,
        "counters": counters,
        "totals": {
            "ads_total": total_ads,
            "ads_published": published_ads,
        },
        "ads": ads,
    }


@router.get("/api/stats/expired-ads")
async def expired_ads(user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    await _ensure_admin(user)
    now = parse_timestamp(get_serbia_time())
    if now is None:
        return {"items": [], "draft_items": []}

    channel_id = normalize_chat_id(PRIVATE_CHANNEL_ID)
    items = []
    draft_items = []

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, user_id, username, description, timestamp, message_ids
            FROM announcements
            WHERE message_ids IS NOT NULL AND message_ids != '[]'
            ORDER BY id DESC
            """
        )
        rows = await cursor.fetchall()

    for ann_id, user_id, username, description, timestamp, message_ids_raw in rows:
        published_at = parse_timestamp(timestamp)
        if published_at is None:
            continue
        age_delta = now - published_at
        if age_delta <= timedelta(days=30):
            continue
        post_link = None
        try:
            message_ids = json.loads(message_ids_raw) if message_ids_raw else []
            root_message_id = message_ids[0] if message_ids else None
            if channel_id is not None and root_message_id:
                post_link = get_private_channel_post_link(channel_id, root_message_id)
        except Exception:
            post_link = None
        items.append(
            {
                "id": ann_id,
                "user_id": user_id,
                "username": username or "",
                "description": description or "",
                "published_at": timestamp,
                "age_days": int(age_delta.days),
                "post_link": post_link,
            }
        )

    async with aiosqlite.connect(DB_PATH) as db:
        drafts_cursor = await db.execute(
            """
            SELECT id, user_id, username, description, updated_at, timestamp
            FROM announcements
            WHERE message_ids IS NULL OR message_ids = '[]'
            ORDER BY id DESC
            """
        )
        draft_rows = await drafts_cursor.fetchall()

    for ann_id, user_id, username, description, updated_at, timestamp in draft_rows:
        draft_items.append(
            {
                "id": ann_id,
                "user_id": user_id,
                "username": username or "",
                "description": description or "",
                "updated_at": updated_at or timestamp,
            }
        )

    return {"items": items, "draft_items": draft_items}


@router.delete("/api/stats/drafts/{ann_id}")
async def delete_admin_draft(ann_id: int, user: Dict[str, Any] = Depends(get_user_from_request)) -> Dict[str, Any]:
    await _ensure_admin(user)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT message_ids FROM announcements WHERE id = ?", (ann_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Draft not found")
        message_ids_raw = row[0]
        if message_ids_raw and str(message_ids_raw).strip() != "[]":
            raise HTTPException(status_code=400, detail="Only drafts can be deleted")

        await db.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
        await db.commit()

    return {"status": "deleted", "id": ann_id}
