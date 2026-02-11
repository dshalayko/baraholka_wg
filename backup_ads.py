import asyncio
import json
import os
from datetime import datetime

import aiosqlite
from pyrogram import Client
from pyrogram.enums import ChatType, MessageMediaType
from config import API_ID, API_HASH

DB_PATH = "announcements.db"
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_NAME = os.path.join(DATA_DIR, "my_session")


import re

def extract_price_and_username(text):
    """Извлекает цену и username из текста объявления."""
    price_pattern = r'Цена\s*(.*?)\n'
    username_pattern = r'Кому писать\s*@(\w+)'

    price_match = re.search(price_pattern, text, re.DOTALL)
    username_match = re.search(username_pattern, text)

    price = price_match.group(1).strip() if price_match else ""
    username = username_match.group(1).strip() if username_match else "None"

    return price, username


def extract_description(text):
    """Извлекает описание до блока с ценой."""
    price_block_start = re.search(r'Цена', text)
    if price_block_start:
        return text[:price_block_start.start()].strip()
    return text.strip()


async def fetch_channel_announcements():
    async with Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH) as app:
        print("🔍 Получаем список чатов...")

        channel_id = None
        async for dialog in app.get_dialogs():
            chat = dialog.chat
            if chat.type == ChatType.CHANNEL:
                channel_id = chat.id
                print(f"✅ Найден канал: {chat.title} (ID: {channel_id})")
                break

        if not channel_id:
            print("❌ Канал не найден!")
            return

        print(f"📥 Извлекаем сообщения из канала ID: {channel_id}")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                description TEXT,
                price TEXT,
                photo_file_ids TEXT,
                message_ids TEXT,
                timestamp TEXT
            )''')

            async for message in app.get_chat_history(channel_id, limit=100):
                if message.text or message.caption:
                    full_text = message.text or message.caption
                    description = extract_description(full_text)
                    price, extracted_username = extract_price_and_username(full_text)

                    # Получаем user_id и username
                    user_id = None
                    if message.from_user:
                        user_id = message.from_user.id
                        username = message.from_user.username or "None"
                    else:
                        user_id = await get_user_id_by_username(app, extracted_username)
                        username = extracted_username or "None"

                    # Обработка фото
                    photos = []
                    if message.media_group_id:
                        try:
                            grouped_msgs = await app.get_media_group(channel_id, message.media_group_id)
                            for grouped_msg in grouped_msgs:
                                if grouped_msg.photo:
                                    photos.append(grouped_msg.photo.file_id)
                        except Exception as e:
                            print(f"⚠️ Ошибка при получении медиа-группы: {e}")
                    elif message.photo:
                        photos.append(message.photo.file_id)

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    try:
                        await db.execute('''INSERT INTO announcements (user_id, username, description, price, photo_file_ids, message_ids, timestamp)
                                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                         (user_id, username, description, price, json.dumps(photos), json.dumps([message.id]), timestamp))
                    except Exception as e:
                        print(f"❌ Ошибка при записи в базу данных (ID сообщения {message.id}): {e}")

            await db.commit()
        print("✅ Объявления успешно сохранены в базу данных.")


async def get_user_id_by_username(app, username):
    """Получает user_id по username, если это возможно."""
    if username and username != "None":
        try:
            user = await app.get_users(username)
            return user.id
        except Exception as e:
            print(f"⚠️ Не удалось найти user_id для @{username}: {e}")
    return None

if __name__ == "__main__":
    asyncio.run(fetch_channel_announcements())
