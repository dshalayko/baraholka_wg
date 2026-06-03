import io
import os
import re
from typing import Optional

from telegram import Bot, InputFile
from telegram.request import HTTPXRequest

import texts as texts_ru
from utils import escape_markdown_v2, get_serbia_time
from webserver.settings import BOT_TOKEN


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

telegram_timeout = float(os.getenv("TELEGRAM_TIMEOUT_SECONDS", "180"))
request = HTTPXRequest(
    connect_timeout=20.0,
    read_timeout=telegram_timeout,
    write_timeout=telegram_timeout,
    pool_timeout=20.0,
)
bot = Bot(BOT_TOKEN, request=request)


def normalize_chat_id(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _escape_markdown_v2_code(text: str) -> str:
    if text is None:
        return ""
    return text.replace("\\", "\\\\").replace("`", "\\`")


def _escape_description_with_styles(text: str) -> str:
    if not text:
        return ""

    placeholders: list[str] = []
    token_template = "\x00STYLE{idx}\x00"

    def _stash_token(rendered: str) -> str:
        idx = len(placeholders)
        placeholders.append(rendered)
        return token_template.format(idx=idx)

    def _stash(match: re.Match[str], marker: str) -> str:
        inner = match.group(1).strip()
        if not inner:
            return match.group(0)
        if marker == "code":
            escaped_inner = _escape_markdown_v2_code(inner)
        else:
            escaped_inner = escape_markdown_v2(inner)
        if marker == "bold":
            rendered = f"*{escaped_inner}*"
        elif marker == "underline":
            rendered = f"__{escaped_inner}__"
        elif marker == "italic":
            rendered = f"_{escaped_inner}_"
        elif marker == "spoiler":
            rendered = f"||{escaped_inner}||"
        elif marker == "code":
            rendered = f"`{escaped_inner}`"
        else:
            rendered = f"~{escaped_inner}~"
        return _stash_token(rendered)

    processed = re.sub(r"`([^`\n]+?)`", lambda m: _stash(m, "code"), text)
    processed = re.sub(r"\*\*(.+?)\*\*", lambda m: _stash(m, "bold"), processed, flags=re.DOTALL)
    processed = re.sub(r"__(.+?)__", lambda m: _stash(m, "underline"), processed, flags=re.DOTALL)
    processed = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", lambda m: _stash(m, "italic"), processed, flags=re.DOTALL)
    processed = re.sub(r"~~(.+?)~~", lambda m: _stash(m, "strike"), processed, flags=re.DOTALL)
    processed = re.sub(r"\|\|(.+?)\|\|", lambda m: _stash(m, "spoiler"), processed, flags=re.DOTALL)

    quoted_lines: list[str] = []
    for line in processed.split("\n"):
        if re.match(r"^\s*>\s?", line):
            body = re.sub(r"^\s*>\s?", "", line, count=1)
            quoted_lines.append(_stash_token(f"> {escape_markdown_v2(body)}" if body else ">"))
            continue
        quoted_lines.append(line)
    processed = "\n".join(quoted_lines)

    escaped = escape_markdown_v2(processed)

    for idx in reversed(range(len(placeholders))):
        escaped = escaped.replace(token_template.format(idx=idx), placeholders[idx])
    return escaped


def format_announcement_text(
    description: str,
    price: str,
    price_in_description: bool,
    username: str,
    contact_info: Optional[str],
    user_display: Optional[str],
    is_updated: bool,
    is_reserved: bool = False,
) -> str:
    description = _escape_description_with_styles(description)
    if is_reserved:
        description = f"ЗАБРОНИРОВАНО\n\n{description}"
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
