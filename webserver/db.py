import aiosqlite

from config import DB_PATH
from webserver.settings import logger


async def ensure_db() -> None:
    logger.info("db: ensure schema")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                description TEXT NOT NULL,
                price TEXT NOT NULL,
                photo_file_ids TEXT,
                message_ids TEXT,
                timestamp TEXT,
                last_published_is_edit INTEGER DEFAULT 0
            )
            """
        )
        cursor = await db.execute("PRAGMA table_info(announcements)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "last_published_is_edit" not in columns:
            await db.execute("ALTER TABLE announcements ADD COLUMN last_published_is_edit INTEGER DEFAULT 0")
        await db.commit()
