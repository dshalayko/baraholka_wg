import aiosqlite
import json

DATABASE_NAME = 'announcements.db'

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                price TEXT NOT NULL,
                photo_file_ids TEXT
            )
        ''')
        await db.commit()

async def save_announcement(description, price, photos):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT INTO announcements (description, price, photo_file_ids)
            VALUES (?, ?, ?)
        ''', (description, price, json.dumps(photos)))
        await db.commit()
