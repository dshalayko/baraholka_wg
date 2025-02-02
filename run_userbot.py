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
            chat_type = chat.type
            chat_title = chat.title or "Без названия"
            chat_id = chat.id

            # Выводим все чаты с указанием их типа
            print(f"Чат: {chat_title} (ID: {chat_id}), Тип: {chat_type}")

            # Ищем супергруппы
            if chat_type == ChatType.SUPERGROUP:
                print(f"✅ Найдена супергруппа: {chat_title} (ID: {chat_id})")
                return

        print("❌ Не найдено ни одной супергруппы!")

asyncio.run(get_supergroup_id())
