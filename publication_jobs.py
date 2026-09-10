"""One durable republish job per announcement, with restart recovery."""
import asyncio
import functools
import inspect
import json
import time

from config import PRIVATE_CHANNEL_ID
from logger import logger
from transfer_store import (announcement_fingerprint, ensure_transfer_schema, execute,
                            file_lock, get_job, query, set_job)

QUIET_SECONDS = 10
REPEAT_CLICK_SECONDS = 60


def post_link(ids):
    if not ids:
        return None
    return f'https://t.me/c/{str(PRIVATE_CHANNEL_ID).removeprefix("-100")}/{ids[0]}'


def job_response(job):
    ids = json.loads(job['destination_ids'])
    return {'post_link':post_link(ids), 'transfer_status':job['phase'],
            'comments_pending':job['phase'] != 'done'}


async def _bot_result(update, job):
    if job['phase'] != 'done':
        message = update.effective_message
        if message:
            english = (getattr(update.effective_user,'language_code',None) or '').startswith('en')
            text = ('Ad published. Comments are still being transferred; the previous post is retained until the transfer is complete.' if english else
                    'Объявление опубликовано. Перенос комментариев ещё выполняется; старый пост сохранён до завершения переноса.')
            await message.reply_text(text)
    return post_link(json.loads(job['destination_ids']))


def guarded_publication(func):
    signature = inspect.signature(func)
    is_web = 'user' in signature.parameters

    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        bound = signature.bind(*args,**kwargs)
        bound.apply_defaults()
        ann_id = int(bound.arguments['ann_id'])
        update = bound.arguments.get('update')
        user_id = bound.arguments['user'].get('id') if is_web else update.effective_user.id
        await ensure_transfer_schema()

        async def fail(message, status=409):
            if is_web:
                from fastapi import HTTPException
                raise HTTPException(status_code=status, detail=message)
            await update.effective_message.reply_text(message)
            return None

        async with file_lock(f'publication-{ann_id}',wait=False) as acquired:
            if not acquired:
                return await fail('Публикация уже выполняется. Дождитесь завершения и обновите список.')
            try:
                fingerprint, sources = await announcement_fingerprint(ann_id,user_id)
            except LookupError:
                return await fail('Announcement not found',404)
            job = await get_job(ann_id)
            if job and job['phase']=='preparing':
                await execute('DELETE FROM publication_jobs WHERE ann_id=?',(ann_id,))
                job = None
            if job and job['phase'] != 'done':
                if not json.loads(job['destination_ids']):
                    # Bot API has no idempotency key. A process may have died
                    # after sending but before committing its response. Never
                    # blindly issue another send in this ambiguous state.
                    return await fail('Результат предыдущей отправки требует проверки администратором. Повторная публикация остановлена, чтобы не создать дубликат.')
                if fingerprint != job['fingerprint']:
                    return await fail('Сначала дождитесь переноса комментариев предыдущего обновления. Новые изменения сохранены, но ещё не опубликованы.')
                return job_response(job) if is_web else await _bot_result(update,job)
            if job and job['fingerprint']==fingerprint and time.time()-job['created_at']<REPEAT_CLICK_SECONDS:
                return job_response(job) if is_web else await _bot_result(update,job)
            now = time.time()
            await execute("INSERT OR REPLACE INTO publication_jobs(ann_id,fingerprint,source_ids,phase,created_at,updated_at) VALUES (?,?,?,'preparing',?,?)",
                          (ann_id,fingerprint,json.dumps(sources),now,now))
            try:
                result = await func(*args,**kwargs)
            except BaseException as exc:
                job = await get_job(ann_id)
                if job['phase']=='preparing':
                    await execute('DELETE FROM publication_jobs WHERE ann_id=?',(ann_id,))
                elif not json.loads(job['destination_ids']):
                    await set_job(ann_id,phase='uncertain',error=f'{type(exc).__name__}: {exc}'[:1000])
                raise
            job = await get_job(ann_id)
            if not json.loads(job['destination_ids']):
                await set_job(ann_id,phase='uncertain',error='Publication returned without recorded message IDs')
                return await fail('Не удалось подтвердить публикацию. Требуется проверка администратора.')
            if not sources:
                await set_job(ann_id,phase='done',error=None)
            job = await get_job(ann_id)
            if is_web:
                return {**(result or {}),**job_response(job)}
            return await _bot_result(update,job)
    return wrapped


async def process_job(ann_id):
    import comments_manager
    async with file_lock(f'publication-{ann_id}',wait=False) as acquired:
        if not acquired:
            return
        job = await get_job(ann_id)
        if not job or job['phase'] not in ('transfer','cleanup') or job['retry_at']>time.time():
            return
        # A deleted advertisement must not keep a background republish alive.
        ad = await query('SELECT id FROM announcements WHERE id=?',(ann_id,),one=True)
        if not ad:
            return
        sources, destinations = json.loads(job['source_ids']), json.loads(job['destination_ids'])
        if not destinations:
            return
        try:
            needs_transfer = job['phase']=='transfer'
            if sources and job['phase']=='cleanup':
                needs_transfer = await comments_manager.channel_message_exists(sources[0])
            if sources and needs_transfer:
                before = await query('SELECT COUNT(*) AS n FROM comment_copies WHERE new_root=(SELECT discussion_message_id FROM discussion_roots WHERE channel_message_id=?)',(destinations[0],),one=True)
                success = await comments_manager.forward_thread_replies(sources[0],destinations[0],raise_errors=True)
                if not success:
                    raise RuntimeError('Comments transfer incomplete; source post retained')
                after = await query('SELECT COUNT(*) AS n FROM comment_copies WHERE new_root=(SELECT discussion_message_id FROM discussion_roots WHERE channel_message_id=?)',(destinations[0],),one=True)
                now = time.time()
                if job['quiet_since'] is None or before['n']!=after['n']:
                    await set_job(ann_id,phase='transfer',quiet_since=now,retry_at=now+QUIET_SECONDS,error=None)
                    return
                if now-job['quiet_since']<QUIET_SECONDS:
                    return
                # This invocation already re-enumerated the old thread twice.
                # Telegram has no atomic freeze-and-move operation; keep the
                # gap from the final enumeration to deletion as small as possible.
                await set_job(ann_id,phase='cleanup',error=None)
            if sources:
                failed = await comments_manager.delete_channel_messages(sources)
                if failed:
                    raise RuntimeError(f'Old post deletion pending: {failed}')
            await set_job(ann_id,phase='done',error=None,retry_at=0)
        except Exception as exc:
            attempts = job['attempts']+1
            from pyrogram.errors import FloodWait
            delay = max(min(3600,30*2**min(attempts-1,7)), exc.value if isinstance(exc,FloodWait) else 0)
            await set_job(ann_id,error=str(exc)[:1000],attempts=attempts,retry_at=time.time()+delay,quiet_since=None)
            logger.exception('publication transfer pending ann_id=%s attempt=%s',ann_id,attempts)


async def transfer_worker():
    await ensure_transfer_schema()
    while True:
        try:
            jobs = await query("SELECT j.ann_id FROM publication_jobs j JOIN announcements a ON a.id=j.ann_id WHERE j.phase IN ('transfer','cleanup') AND j.retry_at<=? ORDER BY j.updated_at LIMIT 50",(time.time(),))
            for job in jobs:
                await process_job(job['ann_id'])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Transfer worker iteration failed')
        await asyncio.sleep(5)


def guarded_mutation(func):
    """Do not let deletion/edit race an in-flight republish in another process."""
    signature = inspect.signature(func)
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        ann_id = int(bound.arguments['ann_id'])
        await ensure_transfer_schema()
        try:
            await announcement_fingerprint(ann_id,bound.arguments['user'].get('id'))
        except LookupError:
            from fastapi import HTTPException
            raise HTTPException(404, 'Announcement not found')
        async with file_lock(f'publication-{ann_id}', wait=False) as acquired:
            job = await get_job(ann_id)
            if not acquired or (job and job['phase'] != 'done'):
                from fastapi import HTTPException
                raise HTTPException(409, 'Дождитесь завершения публикации и переноса комментариев перед изменением или удалением объявления.')
            return await func(*args, **kwargs)
    return wrapped


def guarded_bot_deletion(func):
    @functools.wraps(func)
    async def wrapped(ann_id, context, query, is_editing=False):
        await ensure_transfer_schema()
        async with file_lock(f'publication-{ann_id}', wait=False) as acquired:
            try:
                await announcement_fingerprint(ann_id, query.from_user.id)
            except LookupError:
                return
            job = await get_job(ann_id)
            if not acquired or (job and job['phase'] != 'done'):
                await query.message.reply_text('Дождитесь завершения переноса комментариев перед удалением объявления.')
                return
            return await func(ann_id, context, query, is_editing=is_editing)
    return wrapped
