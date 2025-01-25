import asyncio
from pyrogram import Client

from logger import logger
from config import API_ID, API_HASH

chat_id = -1002212626667  # ID супергруппы

def forward_thread_replies(old_thread_id, new_thread_id):
    logger.info(f"[forward_thread_replies] Запуск функции {old_thread_id},{new_thread_id} ")
    app = Client("my_session", api_id=API_ID, api_hash=API_HASH)

    async def process_replies():
        await app.start()
        found_message_id = None
        new_message_id = None

        async for message in app.get_chat_history(chat_id, limit=1000):
            if hasattr(message, "forward_from_message_id") and message.forward_from_message_id == old_thread_id:
                found_message_id = message.id
                logger.info(f"🔎 Найдено сообщение: ID {found_message_id}, пересланное из {old_thread_id}")
                break

        async for message in app.get_chat_history(chat_id, limit=1000):
            if hasattr(message, "forward_from_message_id") and message.forward_from_message_id == new_thread_id:
                new_message_id = message.id
                logger.info(f"🔎 Найдено куда пересылать сообщение: ID {new_message_id}, пересланное из {new_thread_id}")
                break

        async for message in app.get_chat_history(chat_id, limit=1000):  # Получаем до 1000 сообщений
            if hasattr(message, "reply_to_message_id") and message.reply_to_message_id == found_message_id:
                original_author = message.from_user.first_name if message.from_user else "Аноним"
                username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else ""
                original_text = message.text or "📷 Медиа"

                logger.info(f"📩 Пересылаем сообщение ID {message.id}, которое было ответом на {message.reply_to_message_id}")

                formatted_text = f"{username}\n{original_text}"

                await app.send_message(
                    chat_id=chat_id,
                    text=formatted_text,
                    reply_to_message_id=new_message_id
                )

        await app.stop()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_replies())
