import asyncio
import os
from pyrogram import Client
from pyrogram.enums import ChatType

from config import API_ID, API_HASH

ENV_FILE = ".env"

async def get_supergroup_id():
    async with Client("my_session", api_id=API_ID, api_hash=API_HASH) as app:
        print("Получаем список чатов...")

        async for dialog in app.get_dialogs():
            chat = dialog.chat
            if chat.type == ChatType.SUPERGROUP:
                print(f"Найдена супергруппа: {chat.title} (ID: {chat.id})")
                save_chat_id_to_env(chat.id)
                return

        print("Не найдено ни одной супергруппы!")


def save_chat_id_to_env(chat_id):
    current_chat_id = None

    # Читаем текущий CHAT_ID
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as env_file:
            for line in env_file:
                if line.startswith("CHAT_ID="):
                    current_chat_id = line.strip().split("=")[1]
                    break

    if current_chat_id == str(chat_id):
        print(f"CHAT_ID уже установлен: {chat_id}")
    else:
        # Перезаписываем файл .env
        with open(ENV_FILE, "w") as env_file:
            env_file.write(f"CHAT_ID={chat_id}\n")
        print(f"CHAT_ID обновлён: {chat_id}")


asyncio.run(get_supergroup_id())
