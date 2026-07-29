"""Test users and Telegram initData signing.

The debug server does not bypass webserver.auth — it signs real initData with
the debug BOT_TOKEN, so the production HMAC verification path is exercised
exactly as it is in Telegram. Switching users in the browser just means the
page is rendered with a differently-signed credential.
"""

import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any, Dict, Optional

# Owner is also the admin (devmode.env exports this id as DSHALAYKO_ID).
ADMIN_USER_ID = 900000001

TEST_USERS: Dict[str, Dict[str, Any]] = {
    "owner": {
        "id": ADMIN_USER_ID,
        "first_name": "Оля",
        "last_name": "Владелец",
        "username": "debug_owner",
        "language_code": "ru",
        "allows_write_to_pm": True,
        "_label": "Владелец + админ (ru)",
        "_note": "Владеет большинством тестовых объявлений, видит статистику.",
    },
    "bidder": {
        "id": 900000002,
        "first_name": "Bob",
        "last_name": "Bidder",
        "username": "debug_bidder",
        "language_code": "en",
        "allows_write_to_pm": True,
        "_label": "Ставочник (en)",
        "_note": "Своих объявлений почти нет — им удобно делать ставки.",
    },
    "noname": {
        "id": 900000003,
        "first_name": "Без",
        "last_name": "Юзернейма",
        "language_code": "ru",
        "allows_write_to_pm": False,
        "_label": "Без @username (ru)",
        "_note": "Проверка обязательного поля «Контакты» и запроса write access.",
    },
}

DEFAULT_USER_KEY = "owner"


def resolve_user_key(raw: Optional[str]) -> str:
    key = (raw or "").strip()
    return key if key in TEST_USERS else DEFAULT_USER_KEY


def public_user(key: str) -> Dict[str, Any]:
    """The Telegram-shaped user object, without the debug-only _ fields."""
    return {k: v for k, v in TEST_USERS[key].items() if not k.startswith("_")}


def sign_init_data(user_key: str, start_param: Optional[str] = None) -> str:
    """Build an initData string signed the way Telegram signs it.

    Signed fresh on every page render, so a long-running debug session never
    trips the 24h staleness check in webserver.auth.
    """
    from devmode.env import DEBUG_BOT_TOKEN

    user = public_user(user_key)
    fields = {
        "auth_date": str(int(time.time())),
        "chat_type": "private",
        "query_id": f"DEBUG_{user['id']}",
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    if start_param:
        fields["start_param"] = start_param

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", DEBUG_BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    # urlencode percent-escapes non-ASCII, so the result is safe to send as an
    # HTTP header value — same as what Telegram hands to the Mini App.
    return urllib.parse.urlencode(fields)


def init_data_unsafe(user_key: str, start_param: Optional[str] = None) -> Dict[str, Any]:
    """The parsed mirror of sign_init_data(), for window.Telegram.WebApp."""
    data: Dict[str, Any] = {
        "user": public_user(user_key),
        "auth_date": int(time.time()),
        "chat_type": "private",
        "query_id": f"DEBUG_{TEST_USERS[user_key]['id']}",
    }
    if start_param:
        data["start_param"] = start_param
    return data


def user_directory() -> list:
    """Users as the debug toolbar shows them."""
    return [
        {
            "key": key,
            "label": user["_label"],
            "note": user["_note"],
            "id": user["id"],
            "username": user.get("username"),
            "is_admin": user["id"] == ADMIN_USER_ID,
        }
        for key, user in TEST_USERS.items()
    ]
