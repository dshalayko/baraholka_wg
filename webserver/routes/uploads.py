import asyncio
import io
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from telegram.error import NetworkError, RetryAfter, TelegramError, TimedOut

from utils import get_serbia_time
from webserver.auth import get_user_from_request
from webserver.settings import BUG_CHAT_ID, MEDIA_STORAGE_CHAT_ID, logger
from webserver.telegram_client import bot, normalize_chat_id, upload_photo

router = APIRouter()


@router.post("/api/uploads")
async def upload_files(
    files: List[UploadFile] = File(...),
    user: Dict[str, Any] = Depends(get_user_from_request),
    request: Request = None,
) -> Dict[str, Any]:
    if not MEDIA_STORAGE_CHAT_ID:
        raise HTTPException(status_code=500, detail="MEDIA_STORAGE_CHAT_ID is not set")

    storage_chat_id = normalize_chat_id(MEDIA_STORAGE_CHAT_ID)
    if storage_chat_id is None:
        raise HTTPException(status_code=500, detail="Invalid MEDIA_STORAGE_CHAT_ID")
    bug_chat_id = normalize_chat_id(BUG_CHAT_ID)

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Too many files (max 10)")

    logger.info("upload:start user_id=%s files=%s", user.get("id"), len(files))
    file_ids = []
    for upload in files:
        data = await upload.read()
        filename = upload.filename or "photo.jpg"
        message = None
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                message = await upload_photo(storage_chat_id, data, filename)
                last_error = None
                break
            except RetryAfter as exc:
                last_error = exc
                await asyncio.sleep(min(exc.retry_after + 1, 10))
            except (TimedOut, NetworkError) as exc:
                last_error = exc
                await asyncio.sleep(1 + attempt)
        if last_error is not None:
            error_id = uuid.uuid4().hex[:8]
            logger.warning(
                "upload:timeout error_id=%s user_id=%s filename=%s size=%s error=%s",
                error_id,
                user.get("id"),
                filename,
                len(data),
                last_error,
            )
            if bug_chat_id is not None:
                try:
                    user_id = user.get("id")
                    username = user.get("username") or "None"
                    display_name = " ".join(
                        filter(None, [user.get("first_name"), user.get("last_name")])
                    ).strip() or "None"
                    await bot.send_message(
                        chat_id=bug_chat_id,
                        text=(
                            "BUG REPORT\n"
                            f"Time: {get_serbia_time()}\n"
                            f"User ID: {user_id}\n"
                            f"Username: {username}\n"
                            f"Name: {display_name}\n"
                            "Action: upload_files\n"
                            "Ad ID: None\n"
                            "Status: error\n"
                            f"Error ID: {error_id}\n"
                            "Message: Upload timeout while sending photo to Telegram.\n"
                            f"Detail: file={filename}; size={len(data)} bytes; error={last_error}\n"
                            "Post link: None\n"
                            "Client time: None\n"
                            "Language: None\n"
                            f"User-Agent: {request.headers.get('user-agent') if request else 'None'}\n"
                        ),
                    )
                except TelegramError:
                    logger.exception(
                        "upload:bug_report_failed error_id=%s user_id=%s bug_chat_id=%s",
                        error_id,
                        user.get("id"),
                        bug_chat_id,
                    )
            raise HTTPException(status_code=504, detail=f"Upload timeout: {last_error}")
        if not message.photo:
            raise HTTPException(status_code=400, detail="Failed to upload photo")
        file_id = message.photo[-1].file_id
        file_ids.append(file_id)
        try:
            await bot.delete_message(chat_id=storage_chat_id, message_id=message.message_id)
        except TelegramError as exc:
            logger.warning(
                "upload:cleanup_failed user_id=%s chat_id=%s message_id=%s error=%s",
                user.get("id"),
                storage_chat_id,
                message.message_id,
                exc,
            )

    logger.info("upload:done user_id=%s file_ids=%s", user.get("id"), len(file_ids))
    return {"file_ids": file_ids}
