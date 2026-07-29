"""A fake Bot API that records instead of sending.

webserver.telegram_client.bot is replaced with `bot` from this module before
webserver.app is imported, so every route, photo handler and background job
talks to this object. Nothing here touches the network: channel posts, DMs,
edits and deletions are recorded in an in-memory outbox that the debug UI
renders as a "virtual Telegram", and photos are served from a local store.
"""

import hashlib
import io
import os
import time
import uuid
from collections import deque
from typing import Any, Dict, List, Optional

from devmode.env import (
    DEBUG_BUG_CHAT_ID,
    DEBUG_CHANNEL_ID,
    DEBUG_DISCUSSION_CHAT_ID,
    DEBUG_MEDIA_CHAT_ID,
    DEBUG_PHOTO_DIR,
)
from devmode.users import ADMIN_USER_ID, TEST_USERS


# --------------------------------------------------------------------------
# Photo store
# --------------------------------------------------------------------------

def _photo_path(file_id: str) -> str:
    digest = hashlib.sha256(file_id.encode()).hexdigest()
    return os.path.join(DEBUG_PHOTO_DIR, f"{digest}.bin")


def _extension_of(file_id: str) -> str:
    # file_ids minted here carry their extension after "__".
    if "__" in file_id:
        ext = file_id.rsplit("__", 1)[1]
        if ext.isalnum() and len(ext) <= 5:
            return ext
    return "jpg"


def mint_file_id(prefix: str = "dbg", extension: str = "jpg") -> str:
    ext = extension.lower().lstrip(".")
    if not ext.isalnum() or len(ext) > 5:
        ext = "jpg"
    return f"{prefix}_{uuid.uuid4().hex}__{ext}"


def store_photo(data: bytes, filename: str = "photo.jpg", file_id: Optional[str] = None) -> str:
    """Persist photo bytes locally and return the file_id that maps to them."""
    extension = (filename or "photo.jpg").rsplit(".", 1)[-1] if "." in (filename or "") else "jpg"
    fid = file_id or mint_file_id("dbgup", extension)
    os.makedirs(DEBUG_PHOTO_DIR, exist_ok=True)
    tmp_path = f"{_photo_path(fid)}.{uuid.uuid4().hex}.tmp"
    with open(tmp_path, "wb") as fh:
        fh.write(data)
    os.replace(tmp_path, _photo_path(fid))
    return fid


def _placeholder_png(file_id: str) -> bytes:
    """Deterministic placeholder so unknown file_ids still render an image."""
    from PIL import Image, ImageDraw, ImageFont

    digest = hashlib.sha256(file_id.encode()).digest()
    hue_bg = (40 + digest[0] % 60, 40 + digest[1] % 60, 60 + digest[2] % 80)
    accent = (120 + digest[3] % 120, 120 + digest[4] % 120, 140 + digest[5] % 110)

    width, height = 900, 675
    img = Image.new("RGB", (width, height), hue_bg)
    draw = ImageDraw.Draw(img)
    # Diagonal band so thumbnails are visibly distinct from one another.
    draw.polygon([(0, height), (width, 0), (width, height // 3), (width // 3, height)], fill=accent)

    try:
        font_big = ImageFont.load_default(size=64)
        font_small = ImageFont.load_default(size=26)
    except TypeError:  # very old Pillow
        font_big = font_small = ImageFont.load_default()

    label = file_id.split("__")[0].replace("dbgseed_", "").replace("dbgup_", "")[:18] or "photo"
    draw.text((48, height // 2 - 70), "DEBUG PHOTO", font=font_big, fill=(255, 255, 255))
    draw.text((48, height // 2 + 10), label, font=font_small, fill=(235, 235, 245))
    draw.text((48, height - 60), f"{width}x{height}", font=font_small, fill=(215, 215, 230))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()


def load_photo_bytes(file_id: str) -> bytes:
    """Bytes for a file_id, generating (and caching) a placeholder if unknown."""
    path = _photo_path(file_id)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        pass
    data = _placeholder_png(file_id)
    try:
        store_photo(data, "placeholder.jpg", file_id=file_id)
    except OSError:
        pass
    return data


def ensure_seed_photos(slug: str, count: int) -> List[str]:
    """file_ids for `count` generated photos belonging to a seeded ad."""
    file_ids = []
    for index in range(1, count + 1):
        fid = f"dbgseed_{slug}_{index}__jpg"
        load_photo_bytes(fid)  # materialize on disk
        file_ids.append(fid)
    return file_ids


# --------------------------------------------------------------------------
# Telegram object stand-ins
# --------------------------------------------------------------------------

class FakePhotoSize:
    def __init__(self, file_id: str, width: int = 900, height: int = 675):
        self.file_id = file_id
        self.file_unique_id = file_id[:16]
        self.width = width
        self.height = height
        self.file_size = 100_000


class FakeMessage:
    def __init__(self, message_id: int, chat_id: Any, text: str = "", caption: str = "", photo=None):
        self.message_id = message_id
        self.chat_id = chat_id
        self.id = message_id
        self.text = text
        self.caption = caption
        self.photo = tuple(photo or ())
        self.date = time.time()


class FakeFile:
    def __init__(self, file_id: str):
        self.file_id = file_id
        self.file_unique_id = file_id[:16]
        self.file_path = f"photos/{file_id}.{_extension_of(file_id)}"
        self.file_size = None

    async def download_as_bytearray(self) -> bytearray:
        return bytearray(load_photo_bytes(self.file_id))


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id
        self.is_bot = False


class FakeChatMember:
    def __init__(self, user_id: int, status: str):
        self.user = FakeUser(user_id)
        self.status = status


# --------------------------------------------------------------------------
# Outbox: the "virtual Telegram"
# --------------------------------------------------------------------------

def _chat_label(chat_id: Any) -> str:
    raw = str(chat_id)
    known = {
        DEBUG_CHANNEL_ID: "📢 Канал",
        DEBUG_MEDIA_CHAT_ID: "🗄 Медиа-хранилище",
        DEBUG_BUG_CHAT_ID: "🐞 Баг-чат",
        DEBUG_DISCUSSION_CHAT_ID: "💬 Обсуждения",
    }
    if raw in known:
        return known[raw]
    for user in TEST_USERS.values():
        if raw == str(user["id"]):
            handle = user.get("username")
            who = f"@{handle}" if handle else user["first_name"]
            return f"✉️ ЛС → {who}"
    return f"✉️ ЛС → id:{raw}"


def _buttons_of(reply_markup: Any) -> List[List[Dict[str, str]]]:
    rows: List[List[Dict[str, str]]] = []
    keyboard = getattr(reply_markup, "inline_keyboard", None)
    if not keyboard:
        return rows
    for row in keyboard:
        parsed = []
        for button in row:
            url = getattr(button, "url", None)
            web_app = getattr(button, "web_app", None)
            if not url and web_app is not None:
                url = getattr(web_app, "url", None)
            parsed.append(
                {
                    "text": getattr(button, "text", "") or "",
                    "url": url or "",
                    "callback_data": getattr(button, "callback_data", None) or "",
                }
            )
        if parsed:
            rows.append(parsed)
    return rows


class Outbox:
    """Everything the bot "sent", plus the current state of channel posts."""

    def __init__(self, max_events: int = 500):
        self.events: deque = deque(maxlen=max_events)
        self.channel_posts: Dict[int, Dict[str, Any]] = {}
        self._seq = 0
        self._message_id = 1000

    def next_message_id(self) -> int:
        self._message_id += 1
        return self._message_id

    def reset_message_ids(self) -> None:
        """Only safe when the debug database is being wiped too — otherwise
        stored message_ids would be handed out a second time."""
        self._message_id = 1000

    def reserve_message_ids_up_to(self, value: int) -> None:
        """Never hand out an id at or below `value`.

        Called on restart with the highest message_id already stored in the
        debug database: the counter lives in memory, so without this a freshly
        published post would reuse an id another ad still owns, and editing one
        would rewrite the other's post.
        """
        self._message_id = max(self._message_id, int(value))

    def record(self, kind: str, chat_id: Any, **payload) -> Dict[str, Any]:
        self._seq += 1
        event = {
            "seq": self._seq,
            "at": time.strftime("%H:%M:%S"),
            "kind": kind,
            "chat_id": str(chat_id),
            "chat_label": _chat_label(chat_id),
            "text": payload.get("text", "") or "",
            "photo_file_ids": payload.get("photo_file_ids") or [],
            "message_ids": payload.get("message_ids") or [],
            "buttons": payload.get("buttons") or [],
        }
        self.events.append(event)
        return event

    # Channel state, so the viewer can show posts as they currently look
    # rather than only as an append-only log.
    def put_channel_post(self, message_id: int, text: str, photo_file_ids: List[str], buttons) -> None:
        self.channel_posts[message_id] = {
            "message_id": message_id,
            "text": text or "",
            "photo_file_ids": list(photo_file_ids or []),
            "buttons": buttons or [],
            "deleted": False,
            "edits": 0,
            "updated_at": time.strftime("%H:%M:%S"),
        }

    def edit_channel_post(self, message_id: int, text: str) -> None:
        post = self.channel_posts.get(message_id)
        if post is None:
            self.put_channel_post(message_id, text, [], [])
            post = self.channel_posts[message_id]
        post["text"] = text or ""
        post["edits"] += 1
        post["updated_at"] = time.strftime("%H:%M:%S")

    def delete_channel_post(self, message_id: int) -> None:
        post = self.channel_posts.get(message_id)
        if post is not None:
            post["deleted"] = True
            post["updated_at"] = time.strftime("%H:%M:%S")

    def snapshot(self) -> Dict[str, Any]:
        posts = [p for p in self.channel_posts.values() if not p["deleted"]]
        posts.sort(key=lambda p: p["message_id"], reverse=True)
        deleted = [p for p in self.channel_posts.values() if p["deleted"]]
        deleted.sort(key=lambda p: p["message_id"], reverse=True)
        return {
            "channel_posts": posts,
            "deleted_posts": deleted,
            "events": list(reversed(self.events)),
        }

    def clear(self) -> None:
        self.events.clear()
        self.channel_posts.clear()


outbox = Outbox()


# --------------------------------------------------------------------------
# FakeBot
# --------------------------------------------------------------------------

class FakeBot:
    """Async, kwargs-tolerant stand-in for telegram.Bot."""

    def __init__(self, outbox: Outbox):
        self.outbox = outbox
        self.username = "debug_bot"
        self.id = 700000000

    async def send_message(self, chat_id=None, text=None, reply_markup=None, **kwargs) -> FakeMessage:
        message_id = self.outbox.next_message_id()
        body = text or ""
        buttons = _buttons_of(reply_markup)
        is_channel = str(chat_id) == DEBUG_CHANNEL_ID
        self.outbox.record(
            "channel_post" if is_channel else "dm",
            chat_id,
            text=body,
            message_ids=[message_id],
            buttons=buttons,
        )
        if is_channel:
            self.outbox.put_channel_post(message_id, body, [], buttons)
        return FakeMessage(message_id, chat_id, text=body)

    async def send_photo(self, chat_id=None, photo=None, caption=None, **kwargs) -> FakeMessage:
        data, filename = _bytes_from_input_file(photo)
        file_id = store_photo(data, filename) if data else mint_file_id()
        message_id = self.outbox.next_message_id()
        self.outbox.record(
            "media_upload",
            chat_id,
            text=caption or "",
            photo_file_ids=[file_id],
            message_ids=[message_id],
        )
        return FakeMessage(message_id, chat_id, caption=caption or "", photo=[FakePhotoSize(file_id)])

    async def send_media_group(self, chat_id=None, media=None, **kwargs) -> List[FakeMessage]:
        items = list(media or [])
        file_ids: List[str] = []
        caption = ""
        for item in items:
            raw_media = getattr(item, "media", None)
            if isinstance(raw_media, str):
                file_ids.append(raw_media)
            else:
                data, filename = _bytes_from_input_file(raw_media)
                file_ids.append(store_photo(data, filename) if data else mint_file_id())
            if not caption:
                caption = getattr(item, "caption", "") or ""

        messages = [FakeMessage(self.outbox.next_message_id(), chat_id, caption=caption) for _ in items or [None]]
        message_ids = [m.message_id for m in messages]
        is_channel = str(chat_id) == DEBUG_CHANNEL_ID
        self.outbox.record(
            "channel_album" if is_channel else "album",
            chat_id,
            text=caption,
            photo_file_ids=file_ids,
            message_ids=message_ids,
        )
        if is_channel and message_ids:
            self.outbox.put_channel_post(message_ids[0], caption, file_ids, [])
        return messages

    async def edit_message_caption(self, chat_id=None, message_id=None, caption=None, reply_markup=None, **kwargs):
        body = caption or ""
        self.outbox.record("edit", chat_id, text=body, message_ids=[message_id], buttons=_buttons_of(reply_markup))
        if str(chat_id) == DEBUG_CHANNEL_ID and message_id:
            self.outbox.edit_channel_post(int(message_id), body)
        return FakeMessage(int(message_id or 0), chat_id, caption=body)

    async def edit_message_text(self, chat_id=None, message_id=None, text=None, reply_markup=None, **kwargs):
        body = text or ""
        self.outbox.record("edit", chat_id, text=body, message_ids=[message_id], buttons=_buttons_of(reply_markup))
        if str(chat_id) == DEBUG_CHANNEL_ID and message_id:
            self.outbox.edit_channel_post(int(message_id), body)
        return FakeMessage(int(message_id or 0), chat_id, text=body)

    async def delete_message(self, chat_id=None, message_id=None, **kwargs) -> bool:
        self.outbox.record("delete", chat_id, message_ids=[message_id])
        if str(chat_id) == DEBUG_CHANNEL_ID and message_id:
            self.outbox.delete_channel_post(int(message_id))
        return True

    async def get_file(self, file_id, **kwargs) -> FakeFile:
        return FakeFile(file_id)

    async def get_chat_member(self, chat_id=None, user_id=None, **kwargs) -> FakeChatMember:
        status = "administrator" if user_id == ADMIN_USER_ID else "member"
        return FakeChatMember(user_id, status)

    async def get_chat(self, chat_id=None, **kwargs):
        return FakeChatMember(self.id, "creator")

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None


def _bytes_from_input_file(candidate: Any):
    """Best-effort extraction of (bytes, filename) from a PTB InputFile."""
    if candidate is None:
        return b"", "photo.jpg"
    if isinstance(candidate, (bytes, bytearray)):
        return bytes(candidate), "photo.jpg"
    filename = getattr(candidate, "filename", None) or "photo.jpg"
    for attribute in ("input_file_content", "attach_bytes", "_bytes"):
        data = getattr(candidate, attribute, None)
        if isinstance(data, (bytes, bytearray)):
            return bytes(data), filename
    stream = getattr(candidate, "input_file_content", None) or getattr(candidate, "stream", None)
    if hasattr(stream, "read"):
        try:
            return stream.read(), filename
        except Exception:
            pass
    return b"", filename


bot = FakeBot(outbox)


async def upload_photo(chat_id: int, data: bytes, filename: str) -> FakeMessage:
    """Replacement for webserver.telegram_client.upload_photo.

    Keeps the real bytes so a photo uploaded in the browser is the photo shown
    back in the card, rather than a generated placeholder.
    """
    file_id = store_photo(data, filename)
    message_id = outbox.next_message_id()
    outbox.record(
        "media_upload",
        chat_id,
        text=f"upload: {filename} ({len(data)} bytes)",
        photo_file_ids=[file_id],
        message_ids=[message_id],
    )
    return FakeMessage(message_id, chat_id, photo=[FakePhotoSize(file_id)])


# --------------------------------------------------------------------------
# Comments (Pyrogram userbot) stubs
# --------------------------------------------------------------------------

async def get_discussion_replies_counts(post_message_ids) -> Dict[int, int]:
    """Deterministic pseudo-counts — the real one needs a Pyrogram session."""
    counts = {}
    for raw_id in post_message_ids or []:
        try:
            message_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        counts[message_id] = message_id % 7
    return counts


async def delete_channel_messages(message_ids):
    for message_id in message_ids or []:
        await bot.delete_message(chat_id=DEBUG_CHANNEL_ID, message_id=message_id)
    return True


async def forward_thread_replies(old_thread_id, new_thread_id):
    outbox.record(
        "comments",
        DEBUG_DISCUSSION_CHAT_ID,
        text=f"forward_thread_replies({old_thread_id} → {new_thread_id}) — заглушка в debug-режиме",
    )
    return True
