import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any, Dict

from fastapi import HTTPException, Request

from webserver.settings import BOT_TOKEN, logger

MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60


def _parse_init_data(init_data: str) -> Dict[str, str]:
    return dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))


def _verify_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    data = _parse_init_data(init_data)
    received_hash = data.pop("hash", None)
    if not received_hash:
        logger.warning("auth: missing hash")
        raise HTTPException(status_code=401, detail="Missing hash")

    logger.debug("auth: fields=%s", ",".join(sorted(data.keys())))
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        logger.warning("auth: invalid init data hash")
        raise HTTPException(status_code=401, detail="Invalid init data")

    auth_date_raw = data.get("auth_date")
    try:
        auth_date = int(auth_date_raw) if auth_date_raw is not None else None
    except ValueError:
        logger.warning("auth: invalid auth_date format")
        raise HTTPException(status_code=401, detail="Invalid auth_date")
    if auth_date is None:
        logger.warning("auth: missing auth_date")
        raise HTTPException(status_code=401, detail="Missing auth_date")

    now = int(time.time())
    if abs(now - auth_date) > MAX_INIT_DATA_AGE_SECONDS:
        logger.warning("auth: stale init data auth_date=%s now=%s", auth_date, now)
        raise HTTPException(status_code=401, detail="Expired init data")

    user_raw = data.get("user")
    user = json.loads(user_raw) if user_raw else None
    if not user:
        logger.warning("auth: user not found in init data")
        raise HTTPException(status_code=401, detail="User not found")
    logger.info("auth: ok user_id=%s username=%s", user.get("id"), user.get("username"))
    return user


def get_user_from_request(request: Request) -> Dict[str, Any]:
    # Header only: initData is a 24h bearer credential, so it must never appear
    # in query strings where server/proxy access logs would capture it.
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        logger.warning("auth: missing init data")
        raise HTTPException(status_code=401, detail="Missing init data")
    logger.debug("auth: init_data_len=%s", len(init_data))
    return _verify_init_data(init_data, BOT_TOKEN)
