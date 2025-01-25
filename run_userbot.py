import asyncio
from pyrogram import Client

from config import API_ID, API_HASH

app = Client("my_session", api_id=API_ID, api_hash=API_HASH)
with app:
    asyncio.sleep(10)  # Оставляем время для аутентификации

