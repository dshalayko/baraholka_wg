import io
import os
import re
from typing import Optional

from telegram import Bot, InputFile
from telegram.request import HTTPXRequest

import texts as texts_ru
import texts_en
from utils import escape_markdown_v2, get_serbia_time
from webserver.settings import BOT_TOKEN, BOT_USERNAME, WEBAPP_URL


SUPPORTED_CURRENCIES = ("RSD", "EUR")


def normalize_currency(currency):
    """Return a valid currency code, defaulting to RSD."""
    code = (currency or "RSD").upper()
    return code if code in SUPPORTED_CURRENCIES else "RSD"


def texts_for(language_code):
    """Pick the texts module for a Telegram language_code (English for any
    non-Russian locale, Russian otherwise)."""
    if language_code and not str(language_code).lower().startswith("ru"):
        return texts_en
    return texts_ru


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

    # Stash URLs first so markdown markers inside them (underscores, asterisks,
    # etc.) are not interpreted as formatting. Trailing sentence punctuation is
    # peeled off so it doesn't become part of the link.
    def _stash_url(match: re.Match[str]) -> str:
        url = match.group(0)
        trailing = ""
        while url and url[-1] in ".,;:!?":
            trailing = url[-1] + trailing
            url = url[:-1]
        return _stash_token(escape_markdown_v2(url)) + trailing

    processed = re.sub(r"https?://\S+", _stash_url, text)

    processed = re.sub(r"`([^`\n]+?)`", lambda m: _stash(m, "code"), processed)
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


def make_bid_button_url(ann_id: int) -> str:
    """Build the URL for the bid button in channel posts.
    Uses t.me/bot?startapp=bid_N — opens Mini App directly with start_param + initData.
    Requires the bot's web app to be configured in BotFather (/setmenubutton).
    Falls back to direct WEBAPP_URL if BOT_USERNAME is not configured (dev mode).
    """
    if BOT_USERNAME:
        return f"https://t.me/{BOT_USERNAME}?startapp=bid_{ann_id}"
    return f"{WEBAPP_URL}?bid={ann_id}"


def make_bid_link_md(ann_id: int, language_code=None) -> str:
    """MarkdownV2 inline link placed inside auction captions.
    Albums (media groups) can't carry inline keyboards, so the bid action is a
    clickable link in the text instead of a button. Styled bold + uppercase to
    make it stand out as much as a caption link can."""
    url = make_bid_button_url(ann_id)
    label = texts_for(language_code).AUCTION_BID_LINK_LABEL
    return f"*[{label}]({url})*"


def format_auction_end(auction_end_at, language_code=None) -> str:
    """Turn the stored "2026-07-29 15:18:02" stamp into "29 июл, 15:18".
    Mirrors formatAuctionEnd() in the mini app so the post and the bid screen
    show the same thing. Anything unparsable is passed through as-is."""
    value = str(auction_end_at or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})", value)
    if not match:
        return value
    _year, month, day, hour, minute = (int(part) for part in match.groups())
    months = texts_for(language_code).MONTHS_SHORT
    return f"{day} {months[month - 1]}, {hour:02d}:{minute:02d}"


def format_auction_text(
    description: str,
    username: str,
    contact_info,
    user_display,
    start_price,
    current_price,
    min_step,
    auction_end_at,
    winner_username,
    auction_status,
    language_code=None,
    currency=None,
    buyout_price=None,
) -> str:
    texts = texts_for(language_code)
    description_escaped = _escape_description_with_styles(description)
    cur = normalize_currency(currency)

    def kv(text, value):
        # "Label: *value*" — compact inline pair.
        return escape_markdown_v2(text) + ": *" + escape_markdown_v2(str(value)) + "*"

    def money(value):
        return f"{value} {cur}"

    sep = " · "

    if username != "None":
        contact_block = texts.CONTACT_TEXT + "\n@" + escape_markdown_v2(username)
    else:
        contact_value = (contact_info or "").strip()
        if contact_value:
            contact_block = texts.CONTACT_TEXT + "\n" + escape_markdown_v2(contact_value)
        else:
            display = user_display or texts.ANONYMOUS_NAME
            contact_block = texts.CONTACT_TEXT + "\n" + escape_markdown_v2(display)

    if auction_status == "finished":
        lines = [escape_markdown_v2(texts.AUCTION_FINISHED_HEADER), "", description_escaped, ""]
        parts = []
        if current_price is not None:
            parts.append(kv(texts.AUCTION_FINAL_PRICE, money(current_price)))
        if winner_username:
            parts.append(kv(texts.AUCTION_WINNER, winner_username))
        lines.append(sep.join(parts) if parts else escape_markdown_v2(texts.AUCTION_NO_BIDS_PLACED))
        lines.append("")
        lines.append(contact_block)
    else:
        lines = [escape_markdown_v2(texts.AUCTION_HEADER), "", description_escaped, ""]
        parts = []
        if start_price is not None:
            parts.append(kv(texts.AUCTION_START_PRICE, money(start_price)))
        if current_price is not None:
            parts.append(kv(texts.AUCTION_CURRENT_BID, money(current_price)))
        else:
            parts.append(escape_markdown_v2(texts.AUCTION_NO_BIDS_YET))
        if min_step is not None:
            parts.append(kv(texts.AUCTION_MIN_STEP, money(min_step)))
        if buyout_price is not None:
            parts.append(kv(texts.AUCTION_BUYOUT_PRICE, money(buyout_price)))
        lines.append(sep.join(parts))
        if auction_end_at:
            lines.append(kv(texts.AUCTION_END_AT, format_auction_end(auction_end_at, language_code)))
        lines.append("")
        lines.append(contact_block)

    return "\n".join(lines)
