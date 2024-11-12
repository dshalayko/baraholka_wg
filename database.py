import aiosqlite
import json
from telegram import InputMediaPhoto
from logger import logger  # Импорт логгера
from config import PRIVATE_CHANNEL_ID

# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                message_ids TEXT, -- JSON-массив message_id
                description TEXT NOT NULL,
                price TEXT NOT NULL,
                photo_file_ids TEXT -- JSON-массив file_id фотографий
            )
        ''')
        await db.commit()

# Проверка наличия объявлений у пользователя
async def has_user_ads(user_id: int) -> bool:
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT COUNT(*) FROM announcements WHERE user_id = ?', (user_id,))
        count = await cursor.fetchone()
        return count[0] > 0

# Сохранение нового объявления
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

# Получение объявлений пользователя
async def get_user_announcements(user_id):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('''
            SELECT id, message_ids, description, price, photo_file_ids
            FROM announcements
            WHERE user_id = ?
        ''', (user_id,))
        rows = await cursor.fetchall()
        return rows  # Возвращает (id, message_ids, description, price, photo_file_ids)

# Удаление объявления по ID
async def delete_announcement_by_id(ann_id, context):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if row:
            message_ids = json.loads(row[0])
            for message_id in message_ids:
                try:
                    await context.bot.delete_message(chat_id=PRIVATE_CHANNEL_ID, message_id=message_id)
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")
            await db.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
            await db.commit()

# Получение данных объявления для редактирования
async def get_announcement_for_edit(ann_id):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT description, price, photo_file_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if row:
            description, price, photo_file_ids = row
            photos = json.loads(photo_file_ids) if photo_file_ids else []
            return description, price, photos
        return None

# Обновление описания объявления
async def update_announcement_description(ann_id, new_description):
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('''
            UPDATE announcements SET description = ? WHERE id = ?
        ''', (new_description, ann_id))
        await db.commit()

# Обновление цены объявления
async def update_announcement_price(ann_id, new_price):
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('''
            UPDATE announcements SET price = ? WHERE id = ?
        ''', (new_price, ann_id))
        await db.commit()

# Редактирование объявления (обновление всех данных)
async def edit_announcement(ann_id, new_description, new_price, new_photos, context):
    async with aiosqlite.connect('announcements.db') as db:
        # Удаление старых сообщений
        cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if row:
            old_message_ids = json.loads(row[0])
            for message_id in old_message_ids:
                try:
                    await context.bot.delete_message(chat_id=PRIVATE_CHANNEL_ID, message_id=message_id)
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")

        # Отправка нового объявления
        message_text = f"Описание: {new_description}\nЦена: {new_price}\n\nОбновлено"
        if new_photos:
            media = [InputMediaPhoto(media=photo_id, caption=message_text if idx == 0 else None) for idx, photo_id in enumerate(new_photos)]
            sent_messages = await context.bot.send_media_group(chat_id=PRIVATE_CHANNEL_ID, media=media)
            new_message_ids = [msg.message_id for msg in sent_messages]
        else:
            sent_message = await context.bot.send_message(chat_id=PRIVATE_CHANNEL_ID, text=message_text)
            new_message_ids = [sent_message.message_id]

        # Обновление записи в базе данных
        await db.execute('''
            UPDATE announcements
            SET description = ?, price = ?, message_ids = ?, photo_file_ids = ?
            WHERE id = ?
        ''', (
            new_description,
            new_price,
            json.dumps(new_message_ids),
            json.dumps(new_photos),
            ann_id
        ))
        await db.commit()

        # Формирование ссылки на сообщение в приватном канале
        channel_id_str = str(PRIVATE_CHANNEL_ID)
        if channel_id_str.startswith('-100'):
            channel_id_str = channel_id_str[4:]
        post_link = f"https://t.me/c/{channel_id_str}/{new_message_ids[0]}"
        return post_link

