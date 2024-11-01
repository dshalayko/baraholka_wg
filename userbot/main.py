import logging
import asyncio

from telethon import TelegramClient, events
from config import API_ID, API_HASH, SESSION_NAME, MAIN_BOT_USERNAME
from main_bot.config import USERBOT_ID
from publisher import publish_announcement

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация клиента
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)



async def main():
    await client.start()
    print(f"Userbot запущен и ожидает сообщения от основного бота с username: {MAIN_BOT_USERNAME}")

    # Проверка на получение сообщения "Привет, userbot!" от основного бота
    @client.on(events.NewMessage(from_users=MAIN_BOT_USERNAME))
    async def respond_to_main_bot(event):
        if event.message.text == "Привет, userbot!":
            print("Получено сообщение от основного бота:", event.message.text)
            await event.respond("Привет, основной бот! Это userbot.")
            print("Ответ отправлен основному боту")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())