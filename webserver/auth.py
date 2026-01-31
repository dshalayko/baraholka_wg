import hashlib
import hmac
import json
import urllib.parse
from typing import Any, Dict

from fastapi import HTTPException, Request

from webserver.settings import BOT_TOKEN, LOG_LEVEL, logger


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


def get_user_from_request(request: Request) -> Dict[str, Any]:
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("initData")
    if not init_data:
        logger.warning("auth: missing init data")
        raise HTTPException(status_code=401, detail="Missing init data")
    logger.debug("auth: init_data_len=%s", len(init_data))
    logger.debug("auth: init_data_prefix=%s", init_data[:64])
    return _verify_init_data(init_data, BOT_TOKEN)
