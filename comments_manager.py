import asyncio
import html
import os
import time
from typing import Dict, Iterable

from pyrogram import Client
from pyrogram.enums import MessageEntityType, ParseMode
from pyrogram.errors import FloodWait

from logger import logger
from config import API_ID, API_HASH, CHAT_NAME, CHAT_ID, PRIVATE_CHANNEL_ID

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_PATH = os.path.join(DATA_DIR, "my_session")
_forward_lock = asyncio.Lock()
_comments_count_cache: Dict[int, tuple[int, float]] = {}
_COMMENTS_CACHE_TTL_SECONDS = 30.0


def _normalize_int_chat_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


AUTHOR_ENTITY_TYPES = {
    MessageEntityType.BOLD,
    MessageEntityType.TEXT_LINK,
    MessageEntityType.TEXT_MENTION,
}


async def get_supergroup_id(app, group_name=None):
    return CHAT_ID


def _get_message_text(message):
    return message.text or message.caption or ""


def _get_message_entities(message):
    return message.entities or message.caption_entities or []


def _extract_link_from_entity(entity):
    if getattr(entity, "url", None):
        return entity.url

    user = getattr(entity, "user", None)
    if user and getattr(user, "id", None):
        return f"tg://user?id={user.id}"

    return None


def _looks_like_author_line(line):
    clean_line = line.strip()
    return bool(clean_line) and len(clean_line) <= 120 and "\n" not in clean_line


def _extract_preserved_author(message):
    text = _get_message_text(message)
    if not text or "\n" not in text:
        return None, text

    first_line, body = text.split("\n", 1)
    first_line = first_line.strip()
    if not _looks_like_author_line(first_line):
        return None, text

    first_line_len = len(first_line)
    for entity in _get_message_entities(message):
        if entity.offset == 0 and entity.length >= first_line_len and entity.type in AUTHOR_ENTITY_TYPES:
            return {
                "name": first_line,
                "link": _extract_link_from_entity(entity),
            }, body

    if first_line.lower() == "unknown":
        nested_author, nested_body = _extract_author_from_plain_text(body)
        if nested_author:
            return nested_author, nested_body

    return _extract_author_from_plain_text(text)


def _extract_author_from_plain_text(text):
    if not text or "\n" not in text:
        return None, text

    first_line, body = text.split("\n", 1)
    first_line = first_line.strip().strip("*")
    if not _looks_like_author_line(first_line):
        return None, text

    if first_line.lower() == "unknown":
        return _extract_author_from_plain_text(body)

    link = None
    if first_line.startswith("@") and len(first_line) > 1:
        link = f"https://t.me/{first_line[1:]}"

    return {"name": first_line, "link": link}, body


def _build_author_from_user(user):
    if not user:
        return {"name": "Unknown", "link": None}

    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    username = getattr(user, "username", None)

    name = full_name or (f"@{username}" if username else "Unknown")
    link = f"tg://user?id={user.id}" if getattr(user, "id", None) else None

    return {"name": name, "link": link}


def _format_author_html(author):
    name = html.escape(author["name"])
    link = author.get("link")
    if link:
        return f'<a href="{html.escape(link, quote=True)}">{name}</a>'
    return f"<b>{name}</b>"


def _format_transferred_comment(message, current_user_id=None):
    message_user_id = getattr(getattr(message, "from_user", None), "id", None)
    is_previously_transferred = current_user_id and message_user_id == current_user_id

    author = body = None
    if is_previously_transferred:
        author, body = _extract_preserved_author(message)

    if not author:
        author = _build_author_from_user(message.from_user)
        body = _get_message_text(message)

    escaped_body = html.escape(body or "")
    author_html = _format_author_html(author)
    return f"{author_html}\n{escaped_body}".strip()


async def forward_thread_replies(old_thread_id, new_thread_id):
    logger.info(f"🚀 [forward_thread_replies] Запуск функции с old_thread_id={old_thread_id}, new_thread_id={new_thread_id}")
    app = Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH)

    try:
        await app.start()
        current_user = await app.get_me()
        current_user_id = current_user.id if current_user else None

        chat_id = await get_supergroup_id(app, CHAT_NAME)
        if not chat_id:
            logger.error("❌ [forward_thread_replies] Не удалось получить ID супергруппы.")
            await app.stop()
            return False

        found_message_id = new_message_id = None

        # Поиск старого сообщения
        for attempt in range(5):
            async for message in app.get_chat_history(chat_id):
                if getattr(message, "forward_from_message_id", None) == old_thread_id:
                    found_message_id = message.id
                    logger.info(f"✅ Найдено старое сообщение ID: {found_message_id}")
                    break
            if found_message_id:
                break
            logger.warning(f"⚠️ [forward_thread_replies] Не найдено старое сообщение (попытка {attempt+1}/5), ждем 2 сек...")
            await asyncio.sleep(2)

        if not found_message_id:
            logger.error(f"❌ [forward_thread_replies] Старое сообщение так и не найдено.")
            await app.stop()
            return False

        for attempt in range(5):
            async for message in app.get_chat_history(chat_id):
                if getattr(message, "forward_from_message_id", None) == new_thread_id:
                    new_message_id = message.id
                    logger.info(f"✅ [forward_thread_replies] Найдено новое сообщение ID: {new_message_id}")
                    break
            if new_message_id:
                break
            await asyncio.sleep(2)

        if not new_message_id:
            logger.error(f"❌ [forward_thread_replies] Новое сообщение так и не найдено.")
            await app.stop()
            return False

        # Перенос комментариев
        comments = []
        async for message in app.get_chat_history(chat_id):
            if message.reply_to_message_id == found_message_id:
                comments.append(message)

        logger.info(f"🔄 Отправляем {len(comments)} комментариев в обратном порядке.")
        ordered_comments = list(reversed(comments))
        photo_batch = []
        photo_batch_sender = None
        photo_batch_author = None

        async def flush_photo_batch():
            nonlocal photo_batch, photo_batch_sender, photo_batch_author
            if not photo_batch:
                return
            author_line, full_name, username = photo_batch_author
            await _send_photo_comments(
                app=app,
                chat_id=chat_id,
                reply_to_message_id=new_message_id,
                photo_comments=photo_batch,
                author_line=author_line,
                full_name=full_name,
                username=username,
            )
            photo_batch = []
            photo_batch_sender = None
            photo_batch_author = None

        for comment in ordered_comments:
            try:
                if comment.text:
                    formatted_text = _format_transferred_comment(comment, current_user_id)
                    await app.send_message(
                        chat_id=chat_id,
                        text=formatted_text,
                        reply_to_message_id=new_message_id,
                        parse_mode=ParseMode.HTML,
                    )
                    logger.info(f"📩 Отправлен текстовый комментарий ID {comment.id}")

                elif comment.photo:
                    caption = _format_transferred_comment(comment, current_user_id)
                    await app.send_photo(
                        chat_id=chat_id,
                        photo=comment.photo.file_id,
                        caption=caption,
                        reply_to_message_id=new_message_id,
                        parse_mode=ParseMode.HTML,
                    )
                    logger.info(f"📸 Отправлена фотография ID {comment.id}")

                elif comment.sticker:
                    await app.send_sticker(chat_id=chat_id, sticker=comment.sticker.file_id, reply_to_message_id=new_message_id)
                    logger.info(f"🎨 Отправлен стикер ID {comment.id}")

                else:
                    logger.warning(f"⚠️ Неизвестный тип медиа в сообщении ID {comment.id}")

            except Exception as e:
                logger.error(f"❌ [forward_thread_replies] Ошибка при отправке комментария ID {comment.id}: {e}")

        try:
            await flush_photo_batch()
        except Exception as e:
            if photo_batch:
                logger.error(f"❌ [forward_thread_replies] Ошибка при отправке фотогруппы, последний ID {photo_batch[-1].id}: {e}")
            else:
                logger.error(f"❌ [forward_thread_replies] Ошибка при финальной отправке фотогруппы: {e}")

        await app.stop()
        logger.info(f"✅ [forward_thread_replies] Перенос комментариев завершен успешно.")
        return True

    except Exception as e:
        logger.error(f"❌ Общая ошибка при переносе комментариев: {e}")
        await app.stop()
        raise


async def forward_thread_replies(old_thread_id, new_thread_id):
    async with _forward_lock:
        for attempt in range(3):
            try:
                return await _forward_thread_replies_once(old_thread_id, new_thread_id)
            except Exception as e:
                err_text = str(e).lower()
                if "database is locked" in err_text and attempt < 2:
                    await asyncio.sleep(2 + attempt * 2)
                    continue
                return False

async def get_message_id_by_thread_id(thread_id):
    """Ищет сообщение, у которого message_id == thread_id, и возвращает его. Логирует ВСЕ сообщения в группе."""
    logger.info(f"🔍 [get_message_id_by_thread_id] Поиск сообщения с message_id={thread_id}")

    async with Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH) as app:
        try:
            chat_id = await get_supergroup_id(app, CHAT_NAME)
            if not chat_id:
                logger.error("❌ [get_message_id_by_thread_id] Не удалось получить ID супергруппы.")
                return None

            logger.info(f"📥 [get_message_id_by_thread_id] Получаем историю сообщений из чата {chat_id}...")

            for attempt in range(5):  # 5 попыток с интервалом 2 сек
                found_message = None
                async for message in app.get_chat_history(chat_id):

                    # 🔍 Если message_id совпадает с thread_id
                    if message.id == thread_id:
                        found_message = message.forward_from_message_id

                    if found_message:
                        logger.info(
                            f"✅ [get_message_id_by_thread_id] Найдено сообщение с message_id={found_message} "
                            f"(совпадает с thread_id={thread_id})"
                        )
                        return found_message

                logger.warning(
                    f"⚠️ [get_message_id_by_thread_id] Не найден message_id (попытка {attempt + 1}/5), ждем 2 сек..."
                )
                await asyncio.sleep(2)

            logger.error(f"❌ [get_message_id_by_thread_id] Не найдено сообщение с message_id={thread_id} после 5 попыток.")

        except Exception as e:
            logger.error(f"❌ [get_message_id_by_thread_id] Ошибка при поиске message_id: {e}")
            return None


async def get_discussion_replies_counts(post_message_ids: Iterable[int]) -> Dict[int, int]:
    ids = []
    for raw_id in post_message_ids:
        try:
            value = int(raw_id)
        except (TypeError, ValueError):
            continue
        if value > 0:
            ids.append(value)

    unique_ids = sorted(set(ids))
    if not unique_ids:
        return {}

    channel_id = _normalize_int_chat_id(PRIVATE_CHANNEL_ID)
    if channel_id is None:
        logger.warning("⚠️ [get_discussion_replies_counts] PRIVATE_CHANNEL_ID is not configured")
        return {msg_id: 0 for msg_id in unique_ids}

    now = time.monotonic()
    results: Dict[int, int] = {}
    ids_to_fetch = []
    for msg_id in unique_ids:
        cached = _comments_count_cache.get(msg_id)
        if cached and (now - cached[1]) < _COMMENTS_CACHE_TTL_SECONDS:
            results[msg_id] = cached[0]
            continue
        ids_to_fetch.append(msg_id)

    if not ids_to_fetch:
        return results

    for msg_id in ids_to_fetch:
        results.setdefault(msg_id, 0)

    async with _forward_lock:
        try:
            async with Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH, sleep_threshold=0) as app:
                for msg_id in ids_to_fetch:
                    try:
                        count = await app.get_discussion_replies_count(channel_id, msg_id)
                        safe_count = max(0, int(count or 0))
                        results[msg_id] = safe_count
                        _comments_count_cache[msg_id] = (safe_count, time.monotonic())
                    except FloodWait as exc:
                        logger.warning(
                            "⚠️ [get_discussion_replies_counts] FloodWait %ss on post %s. "
                            "Returning cached/zero value without blocking.",
                            getattr(exc, "value", None) or "unknown",
                            msg_id,
                        )
                        cached = _comments_count_cache.get(msg_id)
                        results[msg_id] = cached[0] if cached else 0
                    except Exception as exc:
                        logger.warning(
                            "⚠️ [get_discussion_replies_counts] Failed to fetch count for post %s: %s",
                            msg_id,
                            exc,
                        )
                        cached = _comments_count_cache.get(msg_id)
                        results[msg_id] = cached[0] if cached else 0
        except Exception as exc:
            logger.warning("⚠️ [get_discussion_replies_counts] Failed to initialize client: %s", exc)

    return results


async def delete_channel_messages(message_ids):
    """Delete channel posts via the user account (Pyrogram). Unlike the Bot API,
    a user/admin account has no 48-hour deletion limit, so old posts can still be
    removed. Returns the list of message ids that still couldn't be deleted."""
    channel_id = _normalize_int_chat_id(PRIVATE_CHANNEL_ID)
    ids = [m for m in (message_ids or []) if m]
    if channel_id is None or not ids:
        return ids
    failed = []
    try:
        async with Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH) as app:
            for mid in ids:
                try:
                    await app.delete_messages(channel_id, mid)
                except Exception as exc:
                    logger.warning("🗑️ [delete_channel_messages] failed mid=%s error=%s", mid, exc)
                    failed.append(mid)
    except Exception as exc:
        logger.warning("🗑️ [delete_channel_messages] client init failed: %s", exc)
        return ids
    return failed
