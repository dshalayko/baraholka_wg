import asyncio
from pyrogram import Client

from logger import logger
from config import API_ID, API_HASH

chat_id = -1002212626667  # ID супергруппы

async def forward_thread_replies(old_thread_id, new_thread_id):
    logger.info(f"🚀 [forward_thread_replies] Запуск функции с old_thread_id={old_thread_id}, new_thread_id={new_thread_id}")
    app = Client("my_session", api_id=API_ID, api_hash=API_HASH)

    try:
        await app.start()
        found_message_id = None
        new_message_id = None

        logger.info(f"⏳ [forward_thread_replies] Ожидание 2 секунды перед началом поиска сообщений...")
        await asyncio.sleep(2)

        # 🔍 Ждём, пока не найдём старое сообщение (old_message_id)
        for attempt in range(5):  # 5 попыток с интервалом 2 сек
            async for message in app.get_chat_history(chat_id, limit=1000):
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
            async for message in app.get_chat_history(chat_id, limit=1000):
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

        async for message in app.get_chat_history(chat_id, limit=1000):
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
