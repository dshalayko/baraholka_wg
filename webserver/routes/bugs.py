from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from telegram.error import TelegramError

from utils import get_serbia_time
from webserver.auth import get_user_from_request
from webserver.settings import BUG_CHAT_ID, logger
from webserver.telegram_client import bot, normalize_chat_id

router = APIRouter()


@router.post("/api/bug-report")
async def report_bug(
    payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_user_from_request)
) -> Dict[str, Any]:
    chat_id = normalize_chat_id(BUG_CHAT_ID)
    if chat_id is None:
        raise HTTPException(status_code=500, detail="BUG_CHAT_ID is not set")

    user_id = user.get("id")
    username = user.get("username") or "None"
    display_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])).strip() or "None"

    message = (
        "BUG REPORT\n"
        f"Time: {get_serbia_time()}\n"
        f"User ID: {user_id}\n"
        f"Username: {username}\n"
        f"Name: {display_name}\n"
        f"Action: {payload.get('action')}\n"
        f"Ad ID: {payload.get('ad_id')}\n"
        f"Status: {payload.get('status')}\n"
        f"Error ID: {payload.get('error_id')}\n"
        f"Message: {payload.get('message')}\n"
        f"Detail: {payload.get('error_detail')}\n"
        f"Post link: {payload.get('post_link')}\n"
        f"Client time: {payload.get('client_time')}\n"
        f"Language: {payload.get('language')}\n"
        f"User-Agent: {payload.get('user_agent')}\n"
    )

    try:
        await bot.send_message(chat_id=chat_id, text=message)
    except TelegramError as exc:
        logger.exception("bug-report failed chat_id=%s user_id=%s", chat_id, user_id)
        raise HTTPException(status_code=502, detail=str(exc))

    logger.info("bug-report sent chat_id=%s user_id=%s action=%s", chat_id, user_id, payload.get("action"))
    return {"status": "sent"}
