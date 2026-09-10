"""Operator recovery for ambiguous Bot API publication results. See docs/comment-transfer.md."""
import argparse
import asyncio
import json
from datetime import timezone

import aiosqlite
from config import DB_PATH, PRIVATE_CHANNEL_ID
from transfer_store import ensure_transfer_schema, file_lock, get_job, query, execute, record_publication, set_job


async def resolve_publication(ann_id, message_ids):
    from comments_manager import userbot_session
    async with file_lock(f'publication-{ann_id}', wait=False) as acquired:
        if not acquired:
            raise RuntimeError('Publication is still running')
        job = await get_job(ann_id)
        if not job or job['phase'] not in ('sending','uncertain') or json.loads(job['destination_ids']):
            raise ValueError('Only an unresolved publication can be reconciled')
        ids = sorted(set(message_ids))
        if not ids or len(ids)>10 or any(mid<=0 for mid in ids) or set(ids)&set(json.loads(job['source_ids'])):
            raise ValueError('Specify the complete NEW post or album, not the old message IDs')
        async with userbot_session() as app:
            messages = await app.get_messages(int(PRIVATE_CHANNEL_ID),ids)
            if len(messages)!=len(ids) or any(not m or getattr(m,'empty',False) for m in messages):
                raise ValueError('Some new messages do not exist in the configured channel')
            for message in messages:
                date = message.date if message.date.tzinfo else message.date.replace(tzinfo=timezone.utc)
                if date.timestamp()<job['created_at']-60:
                    raise ValueError('Selected post predates this publication attempt')
            albums = {getattr(m,'media_group_id',None) for m in messages}
            if len(ids)>1 and (None in albums or len(albums)!=1):
                raise ValueError('Selected messages are not one album')
            if next(iter(albums)) is not None:
                album = await app.get_media_group(int(PRIVATE_CHANNEL_ID),ids[0])
                if sorted(m.id for m in album)!=ids:
                    raise ValueError('Supply every message ID in the album')
        metadata = json.loads(job['publication_updates'] or '{}')
        allowed = {'timestamp','updated_at','last_published_is_edit','auction_status','owner_language_code','auction_end_at'}
        if not metadata.keys()<=allowed:
            raise ValueError('Invalid publication metadata')
        metadata['message_ids'] = json.dumps(ids)
        async with aiosqlite.connect(DB_PATH,timeout=30) as db:
            cursor = await db.execute('UPDATE announcements SET '+','.join(key+'=?' for key in metadata)+' WHERE id=?',(*metadata.values(),ann_id))
            if cursor.rowcount!=1:
                raise ValueError('Announcement no longer exists')
            await record_publication(db,ann_id,ids)
            await db.commit()


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('status',help='Show unfinished jobs and their last errors')
    retry=commands.add_parser('retry',help='Retry an already published transfer after correcting its error')
    retry.add_argument('ann_id',type=int)
    resolve=commands.add_parser('resolve',help='Attach the operator-verified new post to an ambiguous publication')
    resolve.add_argument('ann_id',type=int)
    resolve.add_argument('message_ids',type=int,nargs='+')
    reset=commands.add_parser('reset-unsent',help='ONLY after manually verifying that no new post was sent')
    reset.add_argument('ann_id',type=int)
    reset.add_argument('--confirmed-not-sent',action='store_true',required=True)
    args=parser.parse_args()
    await ensure_transfer_schema()
    if args.command=='status':
        print(json.dumps(await query("SELECT ann_id,phase,source_ids,destination_ids,attempts,retry_at,error FROM publication_jobs WHERE phase!='done'"),ensure_ascii=False,indent=2))
    elif args.command=='resolve':
        await resolve_publication(args.ann_id,args.message_ids)
        print('Publication reconciled. The worker will resume the transfer.')
    else:
        async with file_lock(f'publication-{args.ann_id}',wait=False) as acquired:
            if not acquired:
                raise RuntimeError('Publication is still running')
            job=await get_job(args.ann_id)
            if args.command=='retry':
                if not job or job['phase'] not in ('transfer','cleanup'):
                    raise ValueError('This job needs publication reconciliation, not a transfer retry')
                await set_job(args.ann_id,retry_at=0,quiet_since=None,error=None)
                print('Retry queued.')
            else:
                if not job or job['phase'] not in ('sending','uncertain') or json.loads(job['destination_ids']):
                    raise ValueError('Only an unresolved, unsent publication may be reset')
                await execute('DELETE FROM publication_jobs WHERE ann_id=?',(args.ann_id,))
                print('Unsent attempt reset. The owner can publish again.')


if __name__=='__main__':
    asyncio.run(main())
