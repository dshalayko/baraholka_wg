"""Resumable discussion copying. Never impersonates the original sender."""
import hashlib
import json
import secrets
from datetime import timezone

from pyrogram import raw, types, utils
from pyrogram.enums import MessageEntityType, ParseMode

from config import CHAT_ID, PRIVATE_CHANNEL_ID
from transfer_store import execute, query

MEDIA_TYPES = ('photo', 'video', 'animation', 'document', 'audio', 'voice', 'sticker', 'video_note')

class TransferIncomplete(RuntimeError):
    pass


def utf16len(text):
    return len(text.encode('utf-16-le')) // 2


def serialize_entities(entities):
    result = []
    for entity in entities or []:
        item = {'type': entity.type.name, 'offset': entity.offset, 'length': entity.length}
        for attr in ('url', 'language', 'custom_emoji_id'):
            value = getattr(entity, attr, None)
            if value is not None:
                item[attr] = value
        if getattr(entity, 'user', None):
            item.update(type='TEXT_LINK', url=f'tg://user?id={entity.user.id}')
        result.append(item)
    return result


def split_formatted(text, entities, limit):
    """Split on Unicode code points, slicing Telegram's UTF-16 entity offsets."""
    chunks, current, size = [], [], 0
    for char in text:
        width = utf16len(char)
        if size + width > limit:
            chunks.append(''.join(current))
            current, size = [], 0
        current.append(char)
        size += width
    if current or not chunks:
        chunks.append(''.join(current))
    result, offset = [], 0
    atomic = {'CUSTOM_EMOJI', 'MENTION', 'HASHTAG', 'BOT_COMMAND', 'URL', 'EMAIL', 'PHONE_NUMBER'}
    for chunk in chunks:
        end = offset + utf16len(chunk)
        local = []
        for entity in entities:
            start, stop = entity['offset'], entity['offset'] + entity['length']
            lo, hi = max(start, offset), min(stop, end)
            if lo < hi:
                if entity['type'] in atomic and (lo != start or hi != stop):
                    continue
                local.append(dict(entity, offset=lo-offset, length=hi-lo))
        result.append((chunk, local))
        offset = end
    return result


def media_info(message):
    for kind in MEDIA_TYPES:
        media = getattr(message, kind, None)
        if media:
            return {'kind':kind, 'file_id':media.file_id, 'unique_id':media.file_unique_id,
                    'spoiler':bool(getattr(message, 'has_media_spoiler', False))}
    if getattr(message, 'media', None):
        raise TransferIncomplete(f'Unsupported attachment in comment {message.id}: {message.media}')
    return None


def origin_from_message(message):
    user = getattr(message, 'from_user', None)
    sender_chat = getattr(message, 'sender_chat', None)
    if user:
        name = ' '.join(filter(None, (user.first_name, user.last_name))) or user.username or 'Пользователь'
        author = {'id':user.id, 'name':name, 'link':f'tg://user?id={user.id}'}
    elif sender_chat:
        username = getattr(sender_chat, 'username', None)
        author = {'id':sender_chat.id, 'name':sender_chat.title or 'Канал', 'link':f'https://t.me/{username}' if username else None}
    else:
        author = {'id':None, 'name':'Автор не указан', 'link':None}
    date = message.date
    if date and date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    text = message.text or message.caption or ''
    return {'author':author, 'date':date.isoformat() if date else None,
            'text':str(text), 'entities':serialize_entities(message.entities or message.caption_entities),
            'media':media_info(message)}


async def discussion_root(app, channel_message_id):
    cached = await query('SELECT * FROM discussion_roots WHERE channel_message_id=?', (channel_message_id,), one=True)
    if cached:
        return cached['discussion_message_id']
    message = await app.get_discussion_message(int(PRIVATE_CHANNEL_ID), channel_message_id)
    if not message or getattr(message, 'empty', False) or message.chat.id != int(CHAT_ID):
        raise TransferIncomplete('Discussion root unavailable or linked group changed')
    await execute('INSERT OR REPLACE INTO discussion_roots VALUES (?,?)', (channel_message_id,message.id))
    return message.id


async def snapshot(app, old_root, new_root, user_id):
    """Persist a complete enumeration before sending anything; no history scan."""
    messages = [m async for m in app.get_discussion_replies(int(CHAT_ID), old_root)]
    messages.sort(key=lambda m:m.id)
    seen = set()
    for message in messages:
        if message.id == old_root or getattr(message, 'service', None) or getattr(message, 'empty', False):
            continue
        previous = await query('SELECT * FROM transferred_parts WHERE message_id=?', (message.id,), one=True)
        is_ours = getattr(getattr(message, 'from_user', None), 'id', None) == user_id
        if previous and is_ours and previous['primary_id'] != message.id:
            continue
        source_id = message.id
        seen.add(source_id)
        existing = await query('SELECT * FROM comment_copies WHERE old_root=? AND new_root=? AND source_id=?', (old_root,new_root,source_id), one=True)
        if existing:
            continue
        origin = json.loads(previous['origin']) if previous and is_ours else origin_from_message(message)
        # Refresh expiring file references from the current Telegram message.
        if previous and is_ours and origin.get('media'):
            origin['media'] = media_info(message)
        # One-time compatibility with copies made by the old implementation.
        if is_ours and not previous:
            from comments_manager import _extract_preserved_author
            author, body = _extract_preserved_author(message)
            if author:
                origin['author'] = dict(author, id=None)
                origin['text'], origin['entities'], origin['date'] = body, [], None
        parent = (previous.get('reply_parent') if previous and is_ours else None) or message.reply_to_message_id or old_root
        parent_part = await query('SELECT primary_id FROM transferred_parts WHERE message_id=?', (parent,), one=True)
        if parent_part:
            parent = parent_part['primary_id']
        await execute('INSERT OR IGNORE INTO comment_copies(old_root,new_root,source_id,parent_id,album_id,origin) VALUES (?,?,?,?,?,?)',
                      (old_root,new_root,source_id,parent,str(message.media_group_id) if message.media_group_id else None,json.dumps(origin)))
    return seen


def header(origin):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    author = origin['author']
    name = author['name'][:160]
    date = origin.get('date')
    stamp = datetime.fromisoformat(date).astimezone(ZoneInfo('Europe/Belgrade')).strftime('%d.%m.%Y %H:%M') if date else 'дата не сохранена'
    text = f'{name} · {stamp}\nПеренесено\n'
    entities = [{'type':'BOLD','offset':0,'length':utf16len(name)}]
    if author.get('link'):
        entities.append({'type':'TEXT_LINK','offset':0,'length':utf16len(name),'url':author['link']})
    return text, entities


def marker_url(key, index):
    # A source-message link doubles as a durable reconciliation marker. No
    # technical identifier is displayed in the comment body.
    digest = hashlib.sha256(f'{key}:{index}'.encode()).hexdigest()[:24]
    return f'https://t.me/c/{str(CHAT_ID).removeprefix("-100")}/{key.split(":")[2]}#copy-{digest}'


def formatted_parts(origin, limit, key):
    prefix, prefix_entities = header(origin)
    available = limit - utf16len(prefix)
    result = []
    for i, (body, entities) in enumerate(split_formatted(origin['text'], origin['entities'], available)):
        shifted = [dict(e, offset=e['offset']+utf16len(prefix)) for e in entities]
        marked = prefix_entities + [{'type':'TEXT_LINK','offset':utf16len(prefix)-utf16len('Перенесено\n'),
                                    'length':utf16len('Перенесено'),'url':marker_url(key,i)}]
        result.append({'text':prefix+body,'entities':marked+shifted,'marker':marker_url(key,i),'source_id':int(key.split(':')[2])})
    return result


def message_has_marker(message, marker):
    return any(getattr(e,'url',None) == marker for e in (message.entities or message.caption_entities or []))


async def reconcile(app, root, payload, user_id):
    found = [None] * len(payload['items'])
    async for message in app.get_discussion_replies(int(CHAT_ID), root):
        if getattr(getattr(message,'from_user',None),'id',None) != user_id:
            continue
        for index, item in enumerate(payload['items']):
            if item.get('marker') and message_has_marker(message,item['marker']):
                found[index] = message.id
            elif item.get('bare_media') and message.reply_to_message_id == payload['reply_to']:
                media = getattr(message,item['media']['kind'],None)
                if media and media.file_unique_id == item['media']['unique_id']:
                    found[index] = message.id
    return found


def extract_sent_ids(response, random_ids):
    if isinstance(response, raw.types.UpdateShortSentMessage) and len(random_ids) == 1:
        return [response.id]
    mapped = {u.random_id:u.id for u in getattr(response,'updates',[]) if isinstance(u,raw.types.UpdateMessageID)}
    if all(r in mapped for r in random_ids):
        return [mapped[r] for r in random_ids]
    return None


async def send_operation(app, key, root, payload, user_id):
    row = await query('SELECT * FROM comment_operations WHERE key=?', (key,), one=True)
    if row is None:
        random_ids = [secrets.randbits(63) for _ in payload['items']]
        await execute('INSERT INTO comment_operations(key,new_root,payload,random_ids) VALUES (?,?,?,?)',
                      (key,root,json.dumps(payload),json.dumps(random_ids)))
        row = await query('SELECT * FROM comment_operations WHERE key=?', (key,), one=True)
    payload, random_ids = json.loads(row['payload']), json.loads(row['random_ids'])
    complete = json.loads(row['destination_ids'])
    if complete:
        return complete
    if row['attempted']:
        found = await reconcile(app,root,payload,user_id)
        if all(found):
            await execute('UPDATE comment_operations SET destination_ids=?,error=NULL WHERE key=?', (json.dumps(found),key))
            return found
        if any(found):
            raise TransferIncomplete('Partial album delivery requires reconciliation; old post retained')
    if row['attempted']:
        for item in payload['items']:
            if item.get('media') and item.get('source_id'):
                current = await app.get_messages(int(CHAT_ID),item['source_id'])
                if current and not getattr(current,'empty',False):
                    fresh = media_info(current)
                    if fresh and fresh['unique_id'] == item['media']['unique_id']:
                        item['media'] = fresh
    peer = await app.resolve_peer(int(CHAT_ID))
    prepared = []
    for item in payload['items']:
        entities = [types.MessageEntity(type=MessageEntityType[e['type']], **{k:v for k,v in e.items() if k!='type'}) for e in item['entities']]
        formatted = await utils.parse_text_entities(app,item['text'],ParseMode.DISABLED,entities) if entities else {'message':item['text'],'entities':[]}
        media = utils.get_input_media_from_file_id(item['media']['file_id']) if item.get('media') else None
        if media is not None and item['media'].get('spoiler'):
            media.spoiler = True
        prepared.append((formatted,media))
    common = dict(peer=peer,reply_to_msg_id=payload['reply_to'],silent=True)
    if len(prepared)>1:
        request = raw.functions.messages.SendMultiMedia(**common,multi_media=[
            raw.types.InputSingleMedia(media=media,random_id=random_id,**formatted)
            for (formatted,media),random_id in zip(prepared,random_ids)])
    elif prepared[0][1] is not None:
        request = raw.functions.messages.SendMedia(**common,random_id=random_ids[0],media=prepared[0][1],**prepared[0][0])
    else:
        request = raw.functions.messages.SendMessage(**common,random_id=random_ids[0],no_webpage=True,**prepared[0][0])
    await execute('UPDATE comment_operations SET attempted=1 WHERE key=?',(key,))
    try:
        response = await app.invoke(request)
        ids = extract_sent_ids(response,random_ids)
        if not ids:
            ids = await reconcile(app,root,payload,user_id)
        if not all(ids):
            raise TransferIncomplete('Telegram accepted request without recoverable message IDs')
        await execute('UPDATE comment_operations SET destination_ids=?,error=NULL WHERE key=?',(json.dumps(ids),key))
        return ids
    except Exception as exc:
        await execute('UPDATE comment_operations SET error=? WHERE key=?',(str(exc)[:1000],key))
        raise


async def save_copy(row, primary_id, part_ids, reply_parent):
    from config import DB_PATH
    import aiosqlite
    async with aiosqlite.connect(DB_PATH,timeout=30) as db:
        await db.execute('UPDATE comment_copies SET destination_id=? WHERE old_root=? AND new_root=? AND source_id=?',
                         (primary_id,row['old_root'],row['new_root'],row['source_id']))
        for part_id in part_ids:
            await db.execute('INSERT OR REPLACE INTO transferred_parts VALUES (?,?,?,?)',(part_id,primary_id,row['origin'],reply_parent))
        await db.commit()


def order_replies(rows, root):
    """Parents precede children, including replies to split-message headers.

    A user can answer a sticker header before its media is sent, so the
    canonical parent's message ID is not necessarily smaller than the reply.
    """
    pending = sorted(rows, key=lambda row: row['source_id'])
    source_ids = {row['source_id'] for row in pending}
    known, ordered = {root}, []
    while pending:
        ready = next((row for row in pending if row['parent_id'] not in source_ids or row['parent_id'] in known), None)
        if ready is None:
            raise TransferIncomplete('Cyclic reply relationships; cannot safely restore the thread')
        ordered.append(ready)
        known.add(ready['source_id'])
        pending.remove(ready)
    return ordered


async def copy_rows(app, old_root, new_root, user_id):
    rows = await query('SELECT * FROM comment_copies WHERE old_root=? AND new_root=? ORDER BY source_id',(old_root,new_root))
    rows = order_replies(rows,old_root)
    mapping = {old_root:new_root, **{r['source_id']:r['destination_id'] for r in rows if r['destination_id']}}
    source_ids = {r['source_id'] for r in rows}
    handled = set()
    for row in rows:
        sid = row['source_id']
        if sid in handled or row['destination_id']:
            continue
        parent = row['parent_id']
        if parent in source_ids and parent not in mapping:
            raise TransferIncomplete(f'Parent {parent} has not been copied')
        target = mapping.get(parent,new_root)  # A deleted parent falls back to the root.
        origin = json.loads(row['origin'])
        key = f'{old_root}:{new_root}:{sid}'
        media = origin.get('media')
        # Telegram albums must be sent together, with one stable random_id per item.
        group = [row]
        if row['album_id'] and media and media['kind'] in ('photo','video','audio','document'):
            group = [r for r in rows if r['album_id']==row['album_id'] and r['parent_id']==parent and not r['destination_id']]
        if len(group)>1:
            if len(group)>10:
                raise TransferIncomplete('Album exceeds Telegram limit')
            items, extra_parts = [], []
            for member in group:
                member_origin = json.loads(member['origin'])
                member_key = f'{old_root}:{new_root}:{member["source_id"]}'
                parts = formatted_parts(member_origin,1024,member_key)
                items.append(dict(parts[0],media=member_origin['media']))
                extra_parts.append(parts[1:])
            ids = await send_operation(app,key+':album',new_root,{'items':items,'reply_to':target},user_id)
            # Finish every overflow before committing ANY album member. A retry
            # must recreate the same operation grouping after a crash.
            all_parts = []
            for member, dest, extras in zip(group,ids,extra_parts):
                member_parts = [dest]
                for index,part in enumerate(extras):
                    member_parts += await send_operation(app,f'{old_root}:{new_root}:{member["source_id"]}:extra:{index}',new_root,{'items':[part],'reply_to':dest},user_id)
                all_parts.append(member_parts)
            from config import DB_PATH
            import aiosqlite
            async with aiosqlite.connect(DB_PATH,timeout=30) as db:
                for member,dest,parts in zip(group,ids,all_parts):
                    await db.execute('UPDATE comment_copies SET destination_id=? WHERE old_root=? AND new_root=? AND source_id=?',(dest,old_root,new_root,member['source_id']))
                    for part in parts:
                        await db.execute('INSERT OR REPLACE INTO transferred_parts VALUES (?,?,?,?)',(part,dest,member['origin'],target))
                    mapping[member['source_id']] = dest
                    handled.add(member['source_id'])
                await db.commit()
            continue
        bare = media and media['kind'] in ('sticker','video_note')
        parts = formatted_parts(origin,4096 if not media or bare else 1024,key)
        part_ids = []
        for index,part in enumerate(parts):
            item = dict(part)
            if media and not bare and index==0:
                item['media'] = media
            ids = await send_operation(app,key+f':part:{index}',new_root,{'items':[item],'reply_to':target if not part_ids else part_ids[0]},user_id)
            part_ids.extend(ids)
        primary = part_ids[0]
        if bare:
            item = {'text':'','entities':[],'media':media,'bare_media':True,'source_id':sid}
            ids = await send_operation(app,key+':media',new_root,{'items':[item],'reply_to':primary},user_id)
            primary = ids[0]
            part_ids.extend(ids)
        await save_copy(row,primary,part_ids,target)
        mapping[sid] = primary
        handled.add(sid)


async def transfer_pass(app, old_channel_id, new_channel_id):
    current = await app.get_me()
    await execute("INSERT OR REPLACE INTO transfer_settings VALUES ('userbot_id',?)", (str(current.id),))
    old_root = await discussion_root(app,old_channel_id)
    source = await app.get_messages(int(CHAT_ID),old_root)
    if not source or getattr(source,'empty',False):
        raise TransferIncomplete('Original discussion was deleted; cannot verify completeness')
    new_root = await discussion_root(app,new_channel_id)
    before = await snapshot(app,old_root,new_root,current.id)
    await copy_rows(app,old_root,new_root,current.id)
    after = await snapshot(app,old_root,new_root,current.id)
    pending = await query('SELECT COUNT(*) AS n FROM comment_copies WHERE old_root=? AND new_root=? AND destination_id IS NULL',(old_root,new_root),one=True)
    if pending['n'] or before != after:
        return False
    # Do not count a locally recorded copy as success if Telegram has since
    # removed it. This matters after long outages or manual moderation.
    operations = await query('SELECT destination_ids FROM comment_operations WHERE new_root=?',(new_root,))
    ids = [new_root] + [mid for op in operations for mid in json.loads(op['destination_ids'])]
    for offset in range(0,len(ids),100):
        batch = ids[offset:offset+100]
        messages = await app.get_messages(int(CHAT_ID),batch)
        if len(messages)!=len(batch) or any(not m or getattr(m,'empty',False) for m in messages):
            raise TransferIncomplete('A destination comment was removed; old post retained for review')
    return True
