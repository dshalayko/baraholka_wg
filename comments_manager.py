import asyncio
import os
import time
from typing import Dict, Iterable

from pyrogram import Client
from pyrogram.enums import ChatType
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


async def get_supergroup_id(app, group_name=None):
    return CHAT_ID

async def _forward_thread_replies_once(old_thread_id, new_thread_id):
    logger.info(f"🚀 [forward_thread_replies] Запуск функции с old_thread_id={old_thread_id}, new_thread_id={new_thread_id}")
    app = Client(SESSION_PATH, api_id=API_ID, api_hash=API_HASH)

    try:
        await app.start()

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
        for comment in reversed(comments):
            try:
                first_name = comment.from_user.first_name if comment.from_user else ""
                last_name = comment.from_user.last_name if comment.from_user and comment.from_user.last_name else ""
                full_name = f"{first_name} {last_name}".strip()

                if comment.text:
                    formatted_text = f"**{full_name}**\n{comment.text}"
                    await app.send_message(chat_id=chat_id, text=formatted_text, reply_to_message_id=new_message_id)
                    logger.info(f"📩 Отправлен текстовый комментарий ID {comment.id}")

                elif comment.photo:
                    caption = f"**{full_name}**\n{comment.caption or ''}".strip()
                    await app.send_photo(chat_id=chat_id, photo=comment.photo.file_id, caption=caption, reply_to_message_id=new_message_id)
                    logger.info(f"📸 Отправлена фотография ID {comment.id}")

                elif comment.sticker:
                    await app.send_sticker(chat_id=chat_id, sticker=comment.sticker.file_id, reply_to_message_id=new_message_id)
                    logger.info(f"🎨 Отправлен стикер ID {comment.id}")

                else:
                    logger.warning(f"⚠️ Неизвестный тип медиа в сообщении ID {comment.id}")

            except Exception as e:
                logger.error(f"❌ [forward_thread_replies] Ошибка при отправке комментария ID {comment.id}: {e}")

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
