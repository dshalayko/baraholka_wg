import aiosqlite
import json

from telegram import InputMediaPhoto
from logger import logger  # Импорт логгера

from config import CHANNEL_USERNAME



async def has_user_ads(user_id: int) -> bool:
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT COUNT(*) FROM announcements WHERE user_id = ?', (user_id,))
        count = await cursor.fetchone()
        return count[0] > 0

async def init_db():
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            message_ids TEXT, -- Хранит JSON-массив message_id
            description TEXT NOT NULL,
            price TEXT NOT NULL,
            photo_file_ids TEXT -- Хранит JSON-массив file_id фотографий
            )
        ''')
        await db.commit()

async def save_announcement(user_id, username, message_ids, description, price, photos):
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('''
            INSERT INTO announcements (user_id, username, message_ids, description, price, photo_file_ids)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            username,
            json.dumps(message_ids),
            description,
            price,
            json.dumps(photos)
        ))
        await db.commit()

async def get_user_announcements(user_id):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('''
            SELECT id, message_ids, description, price, photo_file_ids
            FROM announcements
            WHERE user_id = ?
        ''', (user_id,))
        rows = await cursor.fetchall()
        return rows  # Каждая строка содержит (id, message_ids, description, price, photo_file_ids)


async def delete_announcement_by_id(ann_id, context):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if row:
            message_ids = json.loads(row[0])
            for message_id in message_ids:
                try:
                    await context.bot.delete_message(chat_id=CHANNEL_USERNAME, message_id=message_id)
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")
            # Удаляем объявление из базы данных
            await db.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
            await db.commit()


async def update_announcement(ann_id, description, price, message_id):
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('''
            UPDATE announcements SET description = ?, price = ?, message_id = ? WHERE id = ?
        ''', (description, price, message_id, ann_id))
        await db.commit()


async def edit_announcement(ann_id, context):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT description, price, photo_file_ids FROM announcements WHERE id = ?',
                                  (ann_id,))
        row = await cursor.fetchone()
        if row:
            description, price, photo_file_ids = row
            photos = json.loads(photo_file_ids) if photo_file_ids else []
            # Формируем новое сообщение
            user = context.user_data.get('username', 'Неизвестный пользователь')
            message_text = f"Автор: @{user}\nОписание: {context.user_data.get('new_description', description)}\nЦена: {context.user_data.get('new_price', price)}\n\nОбновлено"

            # Удаляем старые сообщения
            cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
            row = await cursor.fetchone()
            if row:
                old_message_ids = json.loads(row[0])
                for message_id in old_message_ids:
                    try:
                        await context.bot.delete_message(chat_id=CHANNEL_USERNAME, message_id=message_id)
                    except Exception as e:
                        logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")

            # Отправляем новое объявление
            if photos:
                media = []
                for idx, photo_id in enumerate(photos):
                    if idx == 0:
                        media.append(InputMediaPhoto(media=photo_id, caption=message_text))
                    else:
                        media.append(InputMediaPhoto(media=photo_id))
                sent_messages = await context.bot.send_media_group(chat_id=CHANNEL_USERNAME, media=media)
                new_message_ids = [msg.message_id for msg in sent_messages]
            else:
                sent_message = await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=message_text)
                new_message_ids = [sent_message.message_id]

            # Обновляем запись в базе данных
            await db.execute('''
                UPDATE announcements
                SET description = ?, price = ?, message_ids = ?, photo_file_ids = ?
                WHERE id = ?
            ''', (
                context.user_data.get('new_description', description),
                context.user_data.get('new_price', price),
                json.dumps(new_message_ids),
                json.dumps(photos),
                ann_id
            ))
            await db.commit()

            # Создаем ссылку на обновленное объявление
            channel_username = CHANNEL_USERNAME.replace('@', '')
            post_link = f"https://t.me/{channel_username}/{new_message_ids[0]}"

            return post_link
        else:
            return None
