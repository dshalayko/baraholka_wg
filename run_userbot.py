import asyncio
import os
from pyrogram import Client
from pyrogram.enums import ChatType

from config import API_ID, API_HASH

ENV_FILE = ".env"
#-1002335133236
#
#-1002288054679
async def get_supergroup_id():
    async with Client("my_session", api_id=API_ID, api_hash=API_HASH) as app:
        print("Получаем список чатов...")

        async for dialog in app.get_dialogs():
            chat = dialog.chat
            if chat.type == ChatType.SUPERGROUP:
                print(f"Найдена супергруппа: {chat.title} (ID: {chat.id})")
                return

        print("Не найдено ни одной супергруппы!")





asyncio.run(get_supergroup_id())
