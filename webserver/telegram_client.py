import io
import re
from typing import Optional

from telegram import Bot, InputFile
from telegram.request import HTTPXRequest

import texts as texts_ru
from utils import escape_markdown_v2, get_serbia_time
from webserver.settings import BOT_TOKEN


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

request = HTTPXRequest(connect_timeout=20.0, read_timeout=60.0, write_timeout=60.0, pool_timeout=20.0)
bot = Bot(BOT_TOKEN, request=request)


def normalize_chat_id(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _escape_description_with_styles(text: str) -> str:
    if not text:
        return ""

    placeholders: list[str] = []

    def _stash(match: re.Match[str], marker: str) -> str:
        inner = match.group(1).strip()
        if not inner:
            return match.group(0)
        escaped_inner = escape_markdown_v2(inner)
        if marker == "bold":
            rendered = f"*{escaped_inner}*"
        elif marker == "italic":
            rendered = f"_{escaped_inner}_"
        else:
            rendered = f"~{escaped_inner}~"
        idx = len(placeholders)
        placeholders.append(rendered)
        return f"\x00STYLE{idx}\x00"

    processed = re.sub(r"\*\*(.+?)\*\*", lambda m: _stash(m, "bold"), text, flags=re.DOTALL)
    processed = re.sub(r"_(.+?)_", lambda m: _stash(m, "italic"), processed, flags=re.DOTALL)
    processed = re.sub(r"~~(.+?)~~", lambda m: _stash(m, "strike"), processed, flags=re.DOTALL)
    escaped = escape_markdown_v2(processed)

    for idx, rendered in enumerate(placeholders):
        escaped = escaped.replace(f"\x00STYLE{idx}\x00", rendered)
    return escaped


def format_announcement_text(
    description: str,
    price: str,
    price_in_description: bool,
    username: str,
    contact_info: Optional[str],
    user_display: Optional[str],
    is_updated: bool,
) -> str:
    description = _escape_description_with_styles(description)
    if username != "None":
        contact_info = f"{texts_ru.CONTACT_TEXT}\n@{escape_markdown_v2(username)}"
    else:
        contact_value = (contact_info or "").strip()
        if contact_value:
            contact_info = f"{texts_ru.CONTACT_TEXT}\n{escape_markdown_v2(contact_value)}"
        else:
            display = user_display or texts_ru.ANONYMOUS_NAME
            contact_info = f"{texts_ru.CONTACT_TEXT}\n{escape_markdown_v2(display)}"
    message = f"{description}\n\n"
    if not price_in_description:
        price = escape_markdown_v2(price)
        message += f"{texts_ru.PRICE_TEXT}\n{price}\n\n"
    message += contact_info

    if is_updated:
        current_time = get_serbia_time()
        message += f"\n\n{texts_ru.UPDATED_TEXT.format(current_time=escape_markdown_v2(current_time))}"

    return message


async def upload_photo(chat_id: int, data: bytes, filename: str):
    return await bot.send_photo(
        chat_id=chat_id,
        photo=InputFile(io.BytesIO(data), filename=filename),
    )
