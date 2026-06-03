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
                price_in_description INTEGER DEFAULT 0,
                contact_info TEXT,
                photo_file_ids TEXT,
                message_ids TEXT,
                timestamp TEXT,
                updated_at TEXT,
                last_published_is_edit INTEGER DEFAULT 0,
                is_reserved INTEGER DEFAULT 0
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS app_stats (
                stat_key TEXT PRIMARY KEY,
                stat_value INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor = await db.execute("PRAGMA table_info(announcements)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "last_published_is_edit" not in columns:
            await db.execute("ALTER TABLE announcements ADD COLUMN last_published_is_edit INTEGER DEFAULT 0")
        if "price_in_description" not in columns:
            await db.execute("ALTER TABLE announcements ADD COLUMN price_in_description INTEGER DEFAULT 0")
        if "contact_info" not in columns:
            await db.execute("ALTER TABLE announcements ADD COLUMN contact_info TEXT")
        if "updated_at" not in columns:
            await db.execute("ALTER TABLE announcements ADD COLUMN updated_at TEXT")
            await db.execute("UPDATE announcements SET updated_at = timestamp WHERE updated_at IS NULL AND timestamp IS NOT NULL")
        if "is_reserved" not in columns:
            await db.execute("ALTER TABLE announcements ADD COLUMN is_reserved INTEGER DEFAULT 0")
        await db.commit()
