"""Durable publication/transfer state, shared by the bot and web process."""
import asyncio
import fcntl
import hashlib
import json
import os
import time
from contextlib import asynccontextmanager

import aiosqlite
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS publication_jobs (
 ann_id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL, source_ids TEXT NOT NULL,
 destination_ids TEXT NOT NULL DEFAULT '[]', phase TEXT NOT NULL,
 created_at REAL NOT NULL, updated_at REAL NOT NULL, retry_at REAL NOT NULL DEFAULT 0,
 attempts INTEGER NOT NULL DEFAULT 0, error TEXT, quiet_since REAL, publication_updates TEXT
);
CREATE TABLE IF NOT EXISTS comment_copies (
 old_root INTEGER NOT NULL, new_root INTEGER NOT NULL, source_id INTEGER NOT NULL,
 parent_id INTEGER, album_id TEXT, origin TEXT NOT NULL, destination_id INTEGER,
 PRIMARY KEY(old_root,new_root,source_id)
);
CREATE INDEX IF NOT EXISTS comment_destination ON comment_copies(destination_id);
CREATE TABLE IF NOT EXISTS comment_operations (
 key TEXT PRIMARY KEY, new_root INTEGER NOT NULL, payload TEXT NOT NULL,
 random_ids TEXT NOT NULL, destination_ids TEXT NOT NULL DEFAULT '[]',
 attempted INTEGER NOT NULL DEFAULT 0, error TEXT
);
CREATE TABLE IF NOT EXISTS discussion_roots (
 channel_message_id INTEGER PRIMARY KEY, discussion_message_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS transferred_parts (
 message_id INTEGER PRIMARY KEY, primary_id INTEGER NOT NULL, origin TEXT NOT NULL, reply_parent INTEGER
);
CREATE TABLE IF NOT EXISTS transfer_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

async def ensure_transfer_schema():
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.executescript(SCHEMA)
        columns = {row[1] for row in await (await db.execute('PRAGMA table_info(transferred_parts)')).fetchall()}
        if 'reply_parent' not in columns:
            await db.execute('ALTER TABLE transferred_parts ADD COLUMN reply_parent INTEGER')
        job_columns = {row[1] for row in await (await db.execute('PRAGMA table_info(publication_jobs)')).fetchall()}
        if 'publication_updates' not in job_columns:
            await db.execute('ALTER TABLE publication_jobs ADD COLUMN publication_updates TEXT')
        await db.commit()

async def query(sql, args=(), *, one=False):
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, args)
        result = await cur.fetchone() if one else await cur.fetchall()
        await db.commit()
        return dict(result) if one and result is not None else ([dict(r) for r in result] if not one else None)

async def execute(sql, args=()):
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute(sql, args)
        await db.commit()

@asynccontextmanager
async def file_lock(name, *, wait=True):
    # flock is released by the OS on process death; unlike leases it cannot
    # expire while a slow Telegram request is still running.
    directory = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), 'transfer_locks')
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, name + '.lock'), 'a') as handle:
        acquired = False
        try:
            while not acquired:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    if not wait:
                        break
                    await asyncio.sleep(.1)
            yield acquired
        finally:
            if acquired:
                fcntl.flock(handle, fcntl.LOCK_UN)

async def get_job(ann_id):
    return await query('SELECT * FROM publication_jobs WHERE ann_id=?', (ann_id,), one=True)

async def set_job(ann_id, **values):
    allowed = {'phase','destination_ids','error','retry_at','attempts','quiet_since'}
    if not values.keys() <= allowed:
        raise ValueError('Invalid job field')
    values['updated_at'] = time.time()
    await execute('UPDATE publication_jobs SET ' + ','.join(k+'=?' for k in values) + ' WHERE ann_id=?', (*values.values(), ann_id))

async def record_publication(db, ann_id, ids):
    # Called in the SAME transaction that updates announcements.message_ids.
    await db.execute("UPDATE publication_jobs SET destination_ids=?, phase='transfer', updated_at=? WHERE ann_id=?", (json.dumps(ids), time.time(), ann_id))

async def announcement_fingerprint(ann_id, user_id):
    row = await query('SELECT * FROM announcements WHERE id=? AND user_id=?', (ann_id,user_id), one=True)
    if row is None:
        raise LookupError('Announcement not found')
    fields = ('description','price','username','photo_file_ids','price_in_description','contact_info','is_reserved','ad_type','start_price','min_step','buyout_price','auction_duration_hours','currency')
    content = {key:row.get(key) for key in fields}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest(), json.loads(row.get('message_ids') or '[]')


async def mark_sending(ann_id, publication_updates=None):
    await execute("UPDATE publication_jobs SET phase='sending',publication_updates=?,updated_at=? WHERE ann_id=?",
                  (json.dumps(publication_updates or {}),time.time(),ann_id))
