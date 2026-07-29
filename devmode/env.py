"""Environment bootstrap for debug mode.

`apply()` must run before config.py or webserver.settings are imported: both
call load_dotenv() at import time, and load_dotenv() does not overwrite keys
that are already in os.environ. Seeding os.environ here therefore makes the
debug values win over .env — which is what keeps debug runs off the real bot
and the real database:

  * BOT_TOKEN points at a bot that does not exist, so even a call that escapes
    the fake-Telegram patching cannot reach the production bot.
  * DB_PATH points at data/debug/debug.db, so the real announcements.db is
    never opened.
  * BOT_USERNAME is blank on purpose: make_bid_button_url() then falls back to
    "{WEBAPP_URL}?bid=N", an http link that opens the bid screen in a plain
    browser instead of a t.me deep link.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG_DIR = os.path.join(BASE_DIR, "data", "debug")
DEBUG_DB_PATH = os.path.join(DEBUG_DIR, "debug.db")
DEBUG_PHOTO_DIR = os.path.join(DEBUG_DIR, "photos")

# Well-formed but nonexistent bot token.
DEBUG_BOT_TOKEN = "123456789:AAdebugLocalBrowserTestingTokenXXXXX"

DEBUG_CHANNEL_ID = "-1002000000001"
DEBUG_MEDIA_CHAT_ID = "-1002000000002"
DEBUG_BUG_CHAT_ID = "-1002000000003"
DEBUG_DISCUSSION_CHAT_ID = "-1002000000004"

_applied = False


def apply(port: int, log_level: str = "INFO") -> str:
    """Seed os.environ with debug values. Returns the debug base URL."""
    global _applied
    base_url = f"http://localhost:{port}"
    if _applied:
        return base_url

    os.makedirs(DEBUG_PHOTO_DIR, exist_ok=True)

    from devmode.users import ADMIN_USER_ID

    overrides = {
        "BOT_TOKEN": DEBUG_BOT_TOKEN,
        "DB_PATH": DEBUG_DB_PATH,
        "PRIVATE_CHANNEL_ID": DEBUG_CHANNEL_ID,
        "MEDIA_STORAGE_CHAT_ID": DEBUG_MEDIA_CHAT_ID,
        "BUG_CHAT_ID": DEBUG_BUG_CHAT_ID,
        "CHAT_ID": DEBUG_DISCUSSION_CHAT_ID,
        "CHAT_NAME": "debug_discussion",
        "INVITE_LINK": f"{base_url}/__debug__/channel",
        "WEBAPP_URL": base_url,
        # Blank → bid links become http URLs this server can serve.
        "BOT_USERNAME": "",
        # Admin screens are gated on these ids.
        "DSHALAYKO_ID": str(ADMIN_USER_ID),
        "SLONSKI_ID": "0",
        # Pyrogram/Telethon credentials are never used (comments are stubbed),
        # but config.py reads them, so give them harmless values.
        "API_ID": "1234567",
        "API_HASH": "debugapihashdebugapihashdebugapi",
        "LOG_LEVEL": log_level,
        "TELEGRAM_TIMEOUT_SECONDS": "5",
    }
    os.environ.update(overrides)
    _applied = True
    return base_url
