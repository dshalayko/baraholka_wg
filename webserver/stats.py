import aiosqlite

from config import DB_PATH
from utils import get_serbia_time


async def increment_stat(stat_key: str, amount: int = 1) -> None:
    if not stat_key or amount <= 0:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO app_stats (stat_key, stat_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(stat_key) DO UPDATE SET
                stat_value = stat_value + excluded.stat_value,
                updated_at = excluded.updated_at
            """,
            (stat_key, amount, get_serbia_time()),
        )
        await db.commit()


async def get_stats(keys: list[str]) -> dict[str, int]:
    if not keys:
        return {}
    placeholders = ",".join("?" for _ in keys)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"SELECT stat_key, stat_value FROM app_stats WHERE stat_key IN ({placeholders})",
            keys,
        )
        rows = await cursor.fetchall()
    data = {key: 0 for key in keys}
    for stat_key, stat_value in rows:
        data[stat_key] = int(stat_value or 0)
    return data
