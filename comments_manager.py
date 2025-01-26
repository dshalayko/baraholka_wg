import asyncio
from pyrogram import Client
from pyrogram.enums import ChatType

from logger import logger
from config import API_ID, API_HASH, CHAT_NAME

async def get_supergroup_id(app, group_name=None):
    """Получает ID супергруппы, в которой находится бот. Если бот в одной супергруппе — берём её сразу."""
    logger.info("🔍 [get_supergroup_id] Получаем список чатов...")

    found_supergroups = []  # Список всех найденных супергрупп

    async for dialog in app.get_dialogs():
        chat_type = dialog.chat.type  # Получаем тип чата
        chat_id = dialog.chat.id
        chat_title = dialog.chat.title or "Без названия"

        # Если это супергруппа, добавляем в список
        if chat_type == ChatType.SUPERGROUP:
            found_supergroups.append((chat_id, chat_title))

    # Если найдена хотя бы одна супергруппа
    if found_supergroups:
        if group_name:
            # Ищем супергруппу по названию
            for chat_id, title in found_supergroups:
                if title == group_name:
                    logger.info(f"✅ [get_supergroup_id] Найдена супергруппа '{group_name}' с ID: {chat_id}")
                    return chat_id

            logger.warning(f"⚠️ [get_supergroup_id] Супергруппа '{group_name}' не найдена среди {len(found_supergroups)} доступных.")
        else:
            # Если не передано `group_name`, но найдена одна супергруппа — используем её
            if len(found_supergroups) == 1:
                chat_id, title = found_supergroups[0]
                logger.info(f"✅ [get_supergroup_id] Используем единственную найденную супергруппу: '{title}' (ID: {chat_id})")
                return chat_id

    logger.error("❌ [get_supergroup_id] Супергруппа не найдена.")
    return None

async def forward_thread_replies(old_thread_id, new_thread_id):
    logger.info(f"🚀 [forward_thread_replies] Запуск функции с old_thread_id={old_thread_id}, new_thread_id={new_thread_id}")
    app = Client("my_session", api_id=API_ID, api_hash=API_HASH)

    try:
        await app.start()

        chat_id = await get_supergroup_id(app, CHAT_NAME)
        if not chat_id:
            logger.error("❌ [forward_thread_replies] Не удалось получить ID супергруппы.")
            await app.stop()
            return False
        found_message_id = None
        new_message_id = None

        # 🔍 Ждём, пока не найдём старое сообщение (old_message_id)
        for attempt in range(5):  # 5 попыток с интервалом 2 сек
            async for message in app.get_chat_history(chat_id):
                if hasattr(message, "forward_from_message_id") and message.forward_from_message_id == old_thread_id:
                    found_message_id = message.id
                    logger.info(f"✅ [forward_thread_replies] Найдено старое сообщение ID: {found_message_id}")
                    break
            if found_message_id:
                break
            logger.warning(f"⚠️ [forward_thread_replies] Не найдено старое сообщение (попытка {attempt+1}/5), ждем 2 сек...")
            await asyncio.sleep(2)

        if not found_message_id:
            logger.error(f"❌ [forward_thread_replies] Старое сообщение так и не найдено.")
            await app.stop()
            return False

        # 🔍 Ждём, пока не найдём новое сообщение (new_message_id)
        for attempt in range(5):  # 5 попыток с интервалом 2 сек
            async for message in app.get_chat_history(chat_id):
                if hasattr(message, "forward_from_message_id") and message.forward_from_message_id == new_thread_id:
                    new_message_id = message.id
                    logger.info(f"✅ [forward_thread_replies] Найдено новое сообщение ID: {new_message_id}")
                    break
            if new_message_id:
                break
            logger.warning(f"⚠️ [forward_thread_replies] Не найдено новое сообщение (попытка {attempt+1}/5), ждем 2 сек...")
            await asyncio.sleep(2)

        if not new_message_id:
            logger.error(f"❌ [forward_thread_replies] Новое сообщение так и не найдено.")
            await app.stop()
            return False

        # 🔄 Перенос всех ответов
        logger.info(f"🔄 [forward_thread_replies] Начинаем перенос комментариев {found_message_id} → {new_message_id}")

        async for message in app.get_chat_history(chat_id):
            if hasattr(message, "reply_to_message_id") and message.reply_to_message_id == found_message_id:
                original_author = message.from_user.first_name if message.from_user else "Аноним"
                username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else ""
                original_text = message.text or "📷 Медиа"

                logger.info(f"📩 [forward_thread_replies] Пересылаем сообщение ID {message.id}, которое было ответом на {message.reply_to_message_id}")

                formatted_text = f"{username}\n{original_text}"

                await app.send_message(
                    chat_id=chat_id,
                    text=formatted_text,
                    reply_to_message_id=new_message_id
                )

        await app.stop()
        logger.info(f"✅ [forward_thread_replies] Перенос комментариев завершен успешно.")
        return True

    except Exception as e:
        logger.error(f"❌ [forward_thread_replies] Ошибка при переносе комментариев: {e}")
        await app.stop()
        return False

async def get_message_id_by_thread_id(thread_id):
    """Ищет сообщение, у которого message_id == thread_id, и возвращает его. Логирует ВСЕ сообщения в группе."""
    logger.info(f"🔍 [get_message_id_by_thread_id] Поиск сообщения с message_id={thread_id}")

    async with Client("my_session", api_id=API_ID, api_hash=API_HASH) as app:
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


