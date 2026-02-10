import io
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


def format_announcement_text(
    description: str,
    price: str,
    price_in_description: bool,
    username: str,
    contact_info: Optional[str],
    user_display: Optional[str],
    is_updated: bool,
) -> str:
    description = escape_markdown_v2(description)
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
