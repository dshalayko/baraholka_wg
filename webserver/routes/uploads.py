import asyncio
import io
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from telegram.error import NetworkError, RetryAfter, TimedOut

from webserver.auth import get_user_from_request
from webserver.settings import MEDIA_STORAGE_CHAT_ID, logger
from webserver.telegram_client import bot, normalize_chat_id, upload_photo

router = APIRouter()


@router.post("/api/uploads")
async def upload_files(
    files: List[UploadFile] = File(...),
    user: Dict[str, Any] = Depends(get_user_from_request),
) -> Dict[str, Any]:
    if not MEDIA_STORAGE_CHAT_ID:
        raise HTTPException(status_code=500, detail="MEDIA_STORAGE_CHAT_ID is not set")

    storage_chat_id = normalize_chat_id(MEDIA_STORAGE_CHAT_ID)
    if storage_chat_id is None:
        raise HTTPException(status_code=500, detail="Invalid MEDIA_STORAGE_CHAT_ID")

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
            raise HTTPException(status_code=504, detail=f"Upload timeout: {last_error}")
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
