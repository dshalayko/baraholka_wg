import asyncio
from pyrogram import Client
from pyrogram.enums import ChatType

from logger import logger
from config import API_ID, API_HASH, CHAT_NAME, CHAT_ID


async def get_supergroup_id(app, group_name=None):
    return CHAT_ID

async def forward_thread_replies(old_thread_id, new_thread_id):
    logger.info(f"🚀 [forward_thread_replies] Запуск функции с old_thread_id={old_thread_id}, new_thread_id={new_thread_id}")
    app = Client("my_session", api_id=API_ID, api_hash=API_HASH)

    try:
        await app.start()

        chat_id = await get_supergroup_id(app, CHAT_NAME)
        if not chat_id:
            logger.error("❌ [forward_thread_replies] Не удалось получить ID супергруппы.")
            await app.stop()
            return False

        found_message_id = new_message_id = None

        # Поиск старого сообщения
        for attempt in range(5):
            async for message in app.get_chat_history(chat_id):
                if getattr(message, "forward_from_message_id", None) == old_thread_id:
                    found_message_id = message.id
                    logger.info(f"✅ Найдено старое сообщение ID: {found_message_id}")
                    break
            if found_message_id:
                break
            logger.warning(f"⚠️ [forward_thread_replies] Не найдено старое сообщение (попытка {attempt+1}/5), ждем 2 сек...")
            await asyncio.sleep(2)

        if not found_message_id:
            logger.error(f"❌ [forward_thread_replies] Старое сообщение так и не найдено.")
            await app.stop()
            return False

        for attempt in range(5):
            async for message in app.get_chat_history(chat_id):
                if getattr(message, "forward_from_message_id", None) == new_thread_id:
                    new_message_id = message.id
                    logger.info(f"✅ [forward_thread_replies] Найдено новое сообщение ID: {new_message_id}")
                    break
            if new_message_id:
                break
            await asyncio.sleep(2)

        if not new_message_id:
            logger.error(f"❌ [forward_thread_replies] Новое сообщение так и не найдено.")
            await app.stop()
            return False

        # Перенос комментариев
        comments = []
        async for message in app.get_chat_history(chat_id):
            if message.reply_to_message_id == found_message_id:
                comments.append(message)

        logger.info(f"🔄 Отправляем {len(comments)} комментариев в обратном порядке.")
        for comment in reversed(comments):
            try:
                first_name = comment.from_user.first_name if comment.from_user else ""
                last_name = comment.from_user.last_name if comment.from_user and comment.from_user.last_name else ""
                full_name = f"{first_name} {last_name}".strip()

                if comment.text:
                    formatted_text = f"**{full_name}**\n{comment.text}"
                    await app.send_message(
                        chat_id=chat_id,
                        text=formatted_text,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"📩 Отправлен текстовый комментарий ID {comment.id}")

                elif comment.photo:
                    caption = f"**{full_name}**\n{comment.caption or ''}".strip()
                    await app.send_photo(
                        chat_id=chat_id,
                        photo=comment.photo.file_id,
                        caption=caption,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"📸 Отправлена фотография ID {comment.id}")

                elif comment.sticker:
                    await app.send_sticker(
                        chat_id=chat_id,
                        sticker=comment.sticker.file_id,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"🎨 Отправлен стикер ID {comment.id}")

                elif comment.animation:
                    caption = f"**{full_name}**\n{comment.caption or ''}".strip()
                    await app.send_animation(
                        chat_id=chat_id,
                        animation=comment.animation.file_id,
                        caption=caption,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"🎞️ Отправлена анимация ID {comment.id}")

                elif comment.video:
                    caption = f"**{full_name}**\n{comment.caption or ''}".strip()
                    await app.send_video(
                        chat_id=chat_id,
                        video=comment.video.file_id,
                        caption=caption,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"🎬 Отправлено видео ID {comment.id}")

                elif comment.document:
                    caption = f"**{full_name}**\n{comment.caption or ''}".strip()
                    await app.send_document(
                        chat_id=chat_id,
                        document=comment.document.file_id,
                        caption=caption,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"📄 Отправлен документ ID {comment.id}")

                elif comment.audio:
                    caption = f"**{full_name}**\n{comment.caption or ''}".strip()
                    await app.send_audio(
                        chat_id=chat_id,
                        audio=comment.audio.file_id,
                        caption=caption,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"🎵 Отправлен аудиофайл ID {comment.id}")

                elif comment.voice:
                    caption = f"**{full_name}**\n{comment.caption or ''}".strip()
                    voice_caption = caption if caption != f"**{full_name}**" else None
                    await app.send_voice(
                        chat_id=chat_id,
                        voice=comment.voice.file_id,
                        caption=voice_caption,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"🎤 Отправлено голосовое сообщение ID {comment.id}")

                elif comment.video_note:
                    await app.send_video_note(
                        chat_id=chat_id,
                        video_note=comment.video_note.file_id,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"📹 Отправлено видео сообщение ID {comment.id}")

                elif comment.location:
                    await app.send_location(
                        chat_id=chat_id,
                        latitude=comment.location.latitude,
                        longitude=comment.location.longitude,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"📍 Отправлена локация ID {comment.id}")

                elif comment.venue:
                    await app.send_venue(
                        chat_id=chat_id,
                        latitude=comment.venue.location.latitude,
                        longitude=comment.venue.location.longitude,
                        title=comment.venue.title,
                        address=comment.venue.address,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"🏢 Отправлена информация о месте ID {comment.id}")

                elif comment.contact:
                    await app.send_contact(
                        chat_id=chat_id,
                        phone_number=comment.contact.phone_number,
                        first_name=comment.contact.first_name,
                        last_name=comment.contact.last_name or '',
                        vcard=comment.contact.vcard or None,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"👤 Отправлен контакт ID {comment.id}")

                else:
                    await app.copy_message(
                        chat_id=chat_id,
                        from_chat_id=chat_id,
                        message_id=comment.id,
                        reply_to_message_id=new_message_id,
                    )
                    logger.info(f"🔄 Скопировано сообщение ID {comment.id}")

            except Exception as e:
                logger.error(f"❌ [forward_thread_replies] Ошибка при отправке комментария ID {comment.id}: {e}")

        await app.stop()
        logger.info(f"✅ [forward_thread_replies] Перенос комментариев завершен успешно.")
        return True

    except Exception as e:
        logger.error(f"❌ Общая ошибка при переносе комментариев: {e}")
        await app.stop()
        return False

async def get_message_id_by_thread_id(thread_id):
    """Ищет сообщение, у которого message_id == thread_id, и возвращает его. Логирует ВСЕ сообщения в группе."""
    logger.info(f"🔍 [get_message_id_by_thread_id] Поиск сообщения с message_id={thread_id}")

    async with Client("my_session", api_id=API_ID, api_hash=API_HASH) as app:
        try:
            chat_id = await get_supergroup_id(app, CHAT_NAME)
            if not chat_id:
                logger.error("❌ [get_message_id_by_thread_id] Не удалось получить ID супергруппы.")
                return None

            logger.info(f"📥 [get_message_id_by_thread_id] Получаем историю сообщений из чата {chat_id}...")

            for attempt in range(5):  # 5 попыток с интервалом 2 сек
                found_message = None
                async for message in app.get_chat_history(chat_id):

                    # 🔍 Если message_id совпадает с thread_id
                    if message.id == thread_id:
                        found_message = message.forward_from_message_id

                    if found_message:
                        logger.info(
                            f"✅ [get_message_id_by_thread_id] Найдено сообщение с message_id={found_message} "
                            f"(совпадает с thread_id={thread_id})"
                        )
                        return found_message

                logger.warning(
                    f"⚠️ [get_message_id_by_thread_id] Не найден message_id (попытка {attempt + 1}/5), ждем 2 сек..."
                )
                await asyncio.sleep(2)

            logger.error(f"❌ [get_message_id_by_thread_id] Не найдено сообщение с message_id={thread_id} после 5 попыток.")

        except Exception as e:
            logger.error(f"❌ [get_message_id_by_thread_id] Ошибка при поиске message_id: {e}")
            return None


