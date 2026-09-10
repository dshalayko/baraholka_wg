import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import aiosqlite
from pyrogram import raw, types
from pyrogram.enums import MessageEntityType
from pyrogram.errors import FloodWait

import config
import comment_transfer as ct
import publication_jobs as jobs
import transfer_store as store


def message(mid, parent=100, text='hello', author=7, **extra):
    values = dict(id=mid,reply_to_message_id=parent,text=text,caption=None,entities=[],caption_entities=[],
                  from_user=NS(id=author,first_name='Анна 😀',last_name=None,username='anna'),sender_chat=None,
                  date=datetime(2026,9,9,12,30,tzinfo=timezone.utc),media=None,media_group_id=None,service=None,empty=False,
                  chat=NS(id=-100123))
    values.update({kind:None for kind in ct.MEDIA_TYPES})
    values.update(extra)
    return NS(**values)


def media(kind, unique='photo'):
    return {kind:NS(file_id=kind+'-'+unique,file_unique_id=unique), 'media':kind}


class FakeClient:
    def __init__(self, source=()):
        self.threads = {100:list(source),200:[],300:[]}
        self.sent = []
        self.delivered = {}
        self.counter = 1000
        self.fail_after_delivery = False
        self.fail_before_number = None
        self.enumerations = 0
        self.late = None

    async def get_me(self):
        return NS(id=99)

    async def get_discussion_message(self, chat, mid):
        return message({10:100,20:200,30:300}[mid])

    async def get_messages(self, chat, mid):
        if isinstance(mid,list):
            return [await self.get_messages(chat,m) for m in mid]
        if mid in self.threads:
            return message(mid)
        for messages in self.threads.values():
            for msg in messages:
                if msg.id==mid:
                    return msg
        return NS(empty=True)

    async def get_discussion_replies(self, chat, root):
        self.enumerations += 1
        snapshot = list(self.threads[root])
        for msg in reversed(snapshot):
            yield msg
        if root==100 and self.late:
            self.threads[100].append(self.late)
            self.late = None

    async def resolve_peer(self, chat):
        return raw.types.InputPeerChannel(channel_id=123,access_hash=1)

    async def invoke(self, request):
        if self.fail_before_number is not None and len(self.sent)==self.fail_before_number:
            self.fail_before_number=None
            raise OSError('temporary failure')
        self.sent.append(request)
        root = request.reply_to_msg_id
        if root not in self.threads:
            root = next(r for r,items in self.threads.items() if any(m.id==root for m in items))
        items = request.multi_media if isinstance(request,raw.functions.messages.SendMultiMedia) else [request]
        updates = []
        for item in items:
            if item.random_id in self.delivered:
                updates.append(raw.types.UpdateMessageID(id=self.delivered[item.random_id],random_id=item.random_id))
                continue
            self.counter += 1
            mid = self.counter
            self.delivered[item.random_id]=mid
            attrs = {}
            item_media = getattr(item,'media',None)
            if item_media:
                attrs = media(item_media.kind,item_media.unique_id)
            parsed = [types.MessageEntity._parse(None,e,{}) for e in item.entities or []]
            msg = message(mid,parent=request.reply_to_msg_id,author=99,text=item.message,entities=parsed,**attrs)
            if item_media:
                msg.caption,msg.caption_entities = msg.text,msg.entities
                msg.text,msg.entities = None,[]
            if len(items)>1:
                msg.media_group_id = 'copied-album'
            self.threads[root].append(msg)
            updates.append(raw.types.UpdateMessageID(id=mid,random_id=item.random_id))
        if self.fail_after_delivery:
            self.fail_after_delivery=False
            raise TimeoutError('response lost after Telegram accepted message')
        return NS(updates=updates)


class TransferTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db=str(Path(self.directory.name)/'test.sqlite')
        patches = [patch.object(store,'DB_PATH',self.db),patch.object(config,'DB_PATH',self.db),
                   patch.object(ct,'CHAT_ID',-100123),patch.object(ct,'PRIVATE_CHANNEL_ID',-100456),
                   patch.object(jobs,'PRIVATE_CHANNEL_ID',-100456)]
        for item in patches:
            item.start();self.addCleanup(item.stop)
        def decode(file_id):
            kind, unique=file_id.split('-',1)
            return NS(kind=kind,unique_id=unique)
        decoder=patch.object(ct.utils,'get_input_media_from_file_id',side_effect=decode)
        decoder.start();self.addCleanup(decoder.stop)
        await store.ensure_transfer_schema()
        await store.execute('CREATE TABLE announcements(id INTEGER PRIMARY KEY,user_id INTEGER,description TEXT,price TEXT,message_ids TEXT,timestamp TEXT)')
        await store.execute("INSERT INTO announcements VALUES (1,7,'chair','10','[10]','2026-09-09')")

    async def test_full_thread_preserves_nested_replies(self):
        app=FakeClient([message(101),message(102,parent=101),message(103,parent=102)])
        self.assertTrue(await ct.transfer_pass(app,10,20))
        copied=app.threads[200]
        self.assertEqual([m.reply_to_message_id for m in copied],[200,copied[0].id,copied[1].id])
        self.assertIn('Анна 😀',copied[0].text)
        self.assertIn('09.09.2026 14:30',copied[0].text)

    async def test_lost_response_reconciles_without_duplicate(self):
        app=FakeClient([message(101)])
        app.fail_after_delivery=True
        with self.assertRaises(TimeoutError):
            await ct.transfer_pass(app,10,20)
        self.assertTrue(await ct.transfer_pass(app,10,20))
        self.assertEqual(len(app.threads[200]),1)
        self.assertEqual(len(app.sent),1)

    async def test_partial_transfer_resumes_parent_mapping(self):
        app=FakeClient([message(101),message(102,parent=101)])
        app.fail_before_number=1
        with self.assertRaises(OSError):
            await ct.transfer_pass(app,10,20)
        self.assertTrue(await ct.transfer_pass(app,10,20))
        self.assertEqual(len(app.threads[200]),2)
        self.assertEqual(app.threads[200][1].reply_to_message_id,app.threads[200][0].id)

    async def test_album_timeout_keeps_album_and_each_author(self):
        app=FakeClient([message(101,text=None,caption='first',media_group_id='album',**media('photo','a')),
                        message(102,text=None,caption='second',media_group_id='album',**media('photo','b')),
                        message(103,parent=102)])
        app.fail_after_delivery=True
        with self.assertRaises(TimeoutError):
            await ct.transfer_pass(app,10,20)
        self.assertTrue(await ct.transfer_pass(app,10,20))
        self.assertIsInstance(app.sent[0],raw.functions.messages.SendMultiMedia)
        self.assertEqual(len(app.threads[200]),3)
        self.assertEqual(app.threads[200][-1].reply_to_message_id,app.threads[200][1].id)

    async def test_repeated_transfer_does_not_stack_author_headers(self):
        app=FakeClient([message(101)])
        await ct.transfer_pass(app,10,20)
        self.assertTrue(await ct.transfer_pass(app,20,30))
        text=app.threads[300][0].text
        self.assertEqual(text.count('Анна 😀'),1)
        self.assertEqual(text.count('Перенесено'),1)
        self.assertTrue(text.endswith('hello'))

    async def test_long_text_utf16_entities_and_fragment_replies(self):
        body='😀'*2400
        bold=types.MessageEntity(type=MessageEntityType.BOLD,offset=0,length=4800)
        app=FakeClient([message(101,text=body,entities=[bold])])
        await ct.transfer_pass(app,10,20)
        parts=app.threads[200]
        self.assertEqual(len(parts),2)
        for part in parts:
            self.assertLessEqual(ct.utf16len(part.text),4096)
            for e in part.entities:
                self.assertLessEqual(e.offset+e.length,ct.utf16len(part.text))
        app.threads[200].append(message(2001,parent=parts[1].id,text='reply'))
        await ct.transfer_pass(app,20,30)
        self.assertEqual(len(app.threads[300]),3)
        self.assertEqual(app.threads[300][-1].reply_to_message_id,app.threads[300][0].id)

    async def test_sticker_header_is_not_duplicated_on_next_republish(self):
        app=FakeClient([message(101,text=None,**media('sticker','cat'))])
        await ct.transfer_pass(app,10,20)
        self.assertEqual(len(app.threads[200]),2)
        await ct.transfer_pass(app,20,30)
        self.assertEqual(len(app.threads[300]),2)
        self.assertIsNotNone(app.threads[300][-1].sticker)

    async def test_new_comment_during_copy_requires_another_pass(self):
        app=FakeClient([message(101)])
        app.late=message(102,parent=101)
        self.assertFalse(await ct.transfer_pass(app,10,20))
        self.assertTrue(await ct.transfer_pass(app,10,20))
        self.assertEqual(len(app.threads[200]),2)

    async def test_unknown_attachment_blocks_completion(self):
        app=FakeClient([message(101,text=None,media='poll')])
        with self.assertRaises(ct.TransferIncomplete):
            await ct.transfer_pass(app,10,20)
        self.assertEqual(len(app.sent),0)

    async def test_missing_source_is_not_treated_as_empty_thread(self):
        app=FakeClient()
        app.get_messages=AsyncMock(return_value=NS(empty=True))
        with self.assertRaises(ct.TransferIncomplete):
            await ct.transfer_pass(app,10,20)

    async def test_file_lock_excludes_second_worker_and_releases(self):
        async with store.file_lock('same') as first:
            async with store.file_lock('same',wait=False) as second:
                self.assertTrue(first);self.assertFalse(second)
        async with store.file_lock('same',wait=False) as third:
            self.assertTrue(third)

    async def make_job(self,phase='transfer'):
        await store.execute("INSERT INTO publication_jobs(ann_id,fingerprint,source_ids,destination_ids,phase,created_at,updated_at) VALUES (1,'test','[10]','[20]',?,0,0)",(phase,))

    async def test_failure_never_deletes_old_post(self):
        await self.make_job()
        with patch('comments_manager.forward_thread_replies',AsyncMock(return_value=False)),patch('comments_manager.delete_channel_messages',AsyncMock()) as delete:
            await jobs.process_job(1)
            delete.assert_not_awaited()
            job=await store.get_job(1)
            self.assertEqual(job['phase'],'transfer')
            self.assertGreater(job['retry_at'],0)

    async def test_worker_waits_for_quiet_period_then_deletes(self):
        await self.make_job()
        with patch('comments_manager.forward_thread_replies',AsyncMock(return_value=True)),patch('comments_manager.delete_channel_messages',AsyncMock(return_value=[])) as delete:
            await jobs.process_job(1)
            delete.assert_not_awaited()
            await store.set_job(1,quiet_since=0,retry_at=0)
            await jobs.process_job(1)
            delete.assert_awaited_once_with([10])
            self.assertEqual((await store.get_job(1))['phase'],'done')

    async def test_flood_wait_controls_retry_time(self):
        await self.make_job()
        import time
        before=time.time()
        with patch('comments_manager.forward_thread_replies',AsyncMock(side_effect=FloodWait(120))):
            await jobs.process_job(1)
        self.assertGreaterEqual((await store.get_job(1))['retry_at'],before+120)

    async def test_double_publish_click_reuses_existing_post(self):
        sends=[]
        @jobs.guarded_publication
        async def publish(ann_id,user):
            sends.append(20)
            async with aiosqlite.connect(self.db) as db:
                await db.execute("UPDATE announcements SET message_ids='[20]' WHERE id=1")
                await store.record_publication(db,ann_id,[20])
                await db.commit()
            return {'post_link':'link'}
        first=await publish(1,{'id':7})
        second=await publish(1,{'id':7})
        self.assertEqual(sends,[20])
        self.assertEqual(first,second)
        self.assertTrue(first['comments_pending'])

    async def test_unknown_publication_outcome_prevents_blind_resend(self):
        sends=[]
        @jobs.guarded_publication
        async def publish(ann_id,user):
            sends.append(20)
            await store.mark_sending(ann_id)
            raise TimeoutError('unknown send result')
        with self.assertRaises(TimeoutError):
            await publish(1,{'id':7})
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            await publish(1,{'id':7})
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(sends,[20])

    async def test_publish_verifies_owner_before_sending(self):
        called=[]
        @jobs.guarded_publication
        async def publish(ann_id,user):
            called.append(1)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            await publish(1,{'id':8})
        self.assertEqual(called,[])

    async def test_mutation_blocked_while_comments_pending(self):
        await self.make_job()
        called=[]
        @jobs.guarded_mutation
        async def remove(ann_id,user):
            called.append(1)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            await remove(1,{'id':7})
        self.assertEqual(called,[])

    async def test_removed_destination_prevents_success(self):
        app=FakeClient([message(101)])
        await ct.transfer_pass(app,10,20)
        app.threads[200].clear()
        with self.assertRaises(ct.TransferIncomplete):
            await ct.transfer_pass(app,10,20)

    async def test_cleanup_failure_rechecks_late_comments(self):
        await self.make_job('cleanup')
        await store.set_job(1,quiet_since=0)
        with patch('comments_manager.channel_message_exists',AsyncMock(return_value=True)),patch('comments_manager.forward_thread_replies',AsyncMock(return_value=False)) as transfer,patch('comments_manager.delete_channel_messages',AsyncMock()) as delete:
            await jobs.process_job(1)
            transfer.assert_awaited_once()
            delete.assert_not_awaited()

    async def test_cleanup_resumes_if_root_already_deleted(self):
        await self.make_job('cleanup')
        with patch('comments_manager.channel_message_exists',AsyncMock(return_value=False)),patch('comments_manager.forward_thread_replies',AsyncMock()) as transfer,patch('comments_manager.delete_channel_messages',AsyncMock(return_value=[])) as delete:
            await jobs.process_job(1)
            transfer.assert_not_awaited()
            delete.assert_awaited_once()
            self.assertEqual((await store.get_job(1))['phase'],'done')

    async def test_validation_failure_before_send_allows_retry(self):
        @jobs.guarded_publication
        async def publish(ann_id,user):
            raise ValueError('invalid content before send')
        with self.assertRaises(ValueError):
            await publish(1,{'id':7})
        self.assertIsNone(await store.get_job(1))

    async def test_media_types_copy_without_losing_content(self):
        for index,kind in enumerate(('video','animation','document','audio','voice','video_note')):
            app=FakeClient([message(110+index,text=None,caption='caption' if kind!='video_note' else None,**media(kind,kind))])
            # Isolate each transfer's destination IDs as Telegram would.
            await store.execute('DELETE FROM comment_copies')
            await store.execute('DELETE FROM comment_operations')
            await store.execute('DELETE FROM transferred_parts')
            self.assertTrue(await ct.transfer_pass(app,10,20))
            self.assertTrue(any(getattr(m,kind,None) for m in app.threads[200]))

    async def test_actual_web_routes_publish_once_and_expose_pending_status(self):
        from fastapi import FastAPI
        import httpx
        from webserver.routes import announcements as routes
        from webserver import db as webdb
        from webserver.auth import get_user_from_request
        await store.execute('DROP TABLE announcements')
        with patch.object(webdb,'DB_PATH',self.db):
            await webdb.ensure_db()
        await store.execute("INSERT INTO announcements(id,user_id,username,description,price,message_ids) VALUES (1,7,'anna','chair','10','[10]')")
        fakebot=NS(send_message=AsyncMock(return_value=NS(message_id=20)))
        app=FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[get_user_from_request]=lambda:{'id':7,'first_name':'Anna'}
        with patch.object(routes,'DB_PATH',self.db),patch.object(routes,'bot',fakebot),patch.object(routes,'PRIVATE_CHANNEL_ID',-100456),patch.object(routes,'increment_stat',AsyncMock()),patch.object(routes,'get_discussion_replies_counts',AsyncMock(return_value={20:2})):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/api/announcements/1/publish')
                self.assertEqual(response.status_code,200,response.text)
                self.assertTrue(response.json()['comments_pending'])
                retry=await client.post('/api/announcements/1/publish')
                self.assertEqual(retry.status_code,200,retry.text)
                fakebot.send_message.assert_awaited_once()
                listing=await client.get('/api/announcements')
                self.assertEqual(listing.status_code,200,listing.text)
                data=listing.json()
                ads=data if isinstance(data,list) else data.get('items',data.get('announcements',[]))
                self.assertTrue(ads[0]['comments_pending'],data)
                deletion=await client.delete('/api/announcements/1')
                self.assertEqual(deletion.status_code,409)

    async def test_parent_with_later_id_is_copied_before_child(self):
        app=FakeClient([message(101,parent=102),message(102,parent=100)])
        self.assertTrue(await ct.transfer_pass(app,10,20))
        self.assertEqual(app.threads[200][1].reply_to_message_id,app.threads[200][0].id)

    async def test_admin_resolves_publication_with_saved_metadata(self):
        from contextlib import asynccontextmanager
        import transfer_admin
        await store.execute("INSERT INTO publication_jobs(ann_id,fingerprint,source_ids,phase,created_at,updated_at) VALUES (1,'test','[10]','uncertain',0,0)")
        await store.mark_sending(1,{'timestamp':'2026-09-10 12:00:00'})
        fake=NS(get_messages=AsyncMock(return_value=[message(20)]))
        @asynccontextmanager
        async def session():
            yield fake
        with patch.object(transfer_admin,'DB_PATH',self.db),patch('comments_manager.userbot_session',session):
            await transfer_admin.resolve_publication(1,[20])
        job=await store.get_job(1)
        self.assertEqual(job['phase'],'transfer')
        self.assertEqual(json.loads(job['destination_ids']),[20])
        ad=await store.query('SELECT * FROM announcements WHERE id=1',one=True)
        self.assertEqual(ad['message_ids'],'[20]')
        self.assertEqual(ad['timestamp'],'2026-09-10 12:00:00')

    async def test_admin_rejects_old_message_as_recovered_post(self):
        import transfer_admin
        await store.execute("INSERT INTO publication_jobs(ann_id,fingerprint,source_ids,phase,created_at,updated_at) VALUES (1,'test','[10]','uncertain',0,0)")
        with self.assertRaises(ValueError):
            await transfer_admin.resolve_publication(1,[10])

    async def test_real_legacy_publisher_records_job_without_deleting(self):
        import announcements as legacy
        await store.execute('ALTER TABLE announcements ADD COLUMN username TEXT')
        await store.execute('ALTER TABLE announcements ADD COLUMN photo_file_ids TEXT')
        await store.execute("UPDATE announcements SET username='anna'")
        fakebot=NS(send_message=AsyncMock(return_value=NS(message_id=20)),delete_message=AsyncMock())
        update=NS(effective_user=NS(id=7,language_code='ru'),effective_message=NS(reply_text=AsyncMock()))
        context=NS(bot=fakebot)
        with patch.object(legacy,'DB_PATH',self.db),patch.object(legacy,'format_announcement_text',AsyncMock(return_value='chair')):
            first=await legacy.publish_announcement(update,context,1)
            second=await legacy.publish_announcement(update,context,1)
        self.assertEqual(first,second)
        fakebot.send_message.assert_awaited_once()
        fakebot.delete_message.assert_not_awaited()
        self.assertEqual((await store.get_job(1))['phase'],'transfer')


if __name__=='__main__':
    unittest.main()
