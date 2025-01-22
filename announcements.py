import json
import logging
import aiosqlite
from datetime import datetime
from telegram import Update, InputMediaPhoto, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import *
from logger import logger
from texts import *
from keyboards import *
from utils import get_serbia_time, get_private_channel_post_link
from database import (get_user_announcements,
                      )

async def create_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создаёт новое объявление в базе данных и сохраняет его ID в context.user_data."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('''
            INSERT INTO announcements (user_id, username, description, price, photo_file_ids)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, "", "", json.dumps([])))
        ann_id = cursor.lastrowid
        await db.commit()

    context.user_data['ann_id'] = ann_id
    context.user_data['photos'] = []
    context.user_data['username'] = username

    await update.message.reply_text(START_NEW_AD)
    return DESCRIPTION


async def adding_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет фотографии к объявлению, с возможностью создания без фото."""
    ann_id = context.user_data.get('ann_id')

    if not ann_id:
        logger.error("❌ [adding_photos] Ошибка: ID объявления не найден.")
        await update.message.reply_text("Ошибка: ID объявления не найден.")
        return CHOOSING

    # Получаем данные объявления из базы
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute(
            'SELECT description, price, photo_file_ids, message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()

        if not row:
            logger.error(f"❌ [adding_photos] Ошибка: объявление с ID {ann_id} не найдено в базе.")
            await update.message.reply_text("Ошибка: объявление не найдено в базе.")
            return CHOOSING

        description, price, photo_file_ids, message_ids_json = row
        photos = json.loads(photo_file_ids) if photo_file_ids else []
        message_ids = json.loads(message_ids_json) if message_ids_json else None

        # Определяем, редактируется ли объявление (если есть message_ids → опубликовано)
        is_editing = bool(message_ids)

    if update.message.photo:
        if len(photos) < 10:
            photo = update.message.photo[-1]
            photos.append(photo.file_id)
            logger.info(f"🖼️ [adding_photos] Добавлено фото: {photo.file_id}, ID объявления: {ann_id}")

            async with aiosqlite.connect('announcements.db') as db:
                await db.execute('UPDATE announcements SET photo_file_ids = ? WHERE id = ?',
                                 (json.dumps(photos), ann_id))
                await db.commit()

            if len(photos) == 1:
                await update.message.reply_text(ADD_PHOTO_TEXT, reply_markup=finish_photo_markup_with_cancel)
        else:
            await update.message.reply_text(MAX_PHOTOS_REACHED)

    elif update.message.text in [NO_PHOTO_AD, FINISH_PHOTO_UPLOAD]:
        logger.info(f"📸 [adding_photos] Завершение загрузки фото, ID объявления: {ann_id}")
        await update.message.reply_text(PROCESSING_PHOTOS, reply_markup=ReplyKeyboardRemove())

        if not description or not price:
            logger.warning(f"⚠️ [adding_photos] Описание или цена отсутствуют в базе, ID объявления: {ann_id}")
            await update.message.reply_text(DESC_PRICE_REQUIRED)
            return ADDING_PHOTOS

        # Показываем предпросмотр (теперь is_editing берётся из базы)
        logger.info(f"📺 [adding_photos] Показываем предпросмотр, is_editing={is_editing}, ID объявления: {ann_id}")
        await send_preview(update, context, editing=is_editing)
        return CONFIRMATION

    else:
        logger.warning(
            f"⚠️ [adding_photos] Непонятная команда, ожидаем фото или завершение загрузки, ID объявления: {ann_id}")
        await update.message.reply_text(SEND_PHOTO_OR_FINISH_OR_NO_PHOTO)

    return ADDING_PHOTOS


async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение и обновление описания объявления в БД."""
    ann_id = context.user_data.get('ann_id')

    if not ann_id:
        logger.error("❌ [description_received] Ошибка: ID объявления не найден.")
        await update.message.reply_text("Ошибка: ID объявления не найден.")
        return CHOOSING

    description = update.message.text.strip()
    logger.info(f"✏️ [description_received] Введено новое описание: {description}, ID объявления: {ann_id}")

    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('UPDATE announcements SET description = ? WHERE id = ?', (description, ann_id))
        await db.commit()

    if context.user_data.get('is_editing', False):
        logger.info(f"📺 [description_received] Показываем предпросмотр после редактирования, ID объявления: {ann_id}")
        await send_preview(update, context, editing=True)
        return CHOOSING

    await update.message.reply_text('Принято! Теперь укажите цену.')
    return EDIT_PRICE

async def price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"💰 [price_received] начало")

    """Получение и обновление цены объявления в БД."""
    ann_id = context.user_data.get('ann_id')

    if not ann_id:
        logger.error("❌ [price_received] Ошибка: ID объявления не найден.")
        await update.message.reply_text("Ошибка: ID объявления не найден.")
        return CHOOSING

    price = update.message.text.strip()
    logger.info(f"💰 [price_received] Введена новая цена: {price}, ID объявления: {ann_id}")

    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('UPDATE announcements SET price = ? WHERE id = ?', (price, ann_id))
        await db.commit()

    if context.user_data.get('is_editing', False):
        logger.info(f"📺 [price_received] Показываем предпросмотр после редактирования, ID объявления: {ann_id}")
        await send_preview(update, context, editing=True)
        return CONFIRMATION

    await update.message.reply_text(ASK_FOR_PHOTOS, reply_markup=photo_markup_with_cancel, parse_mode='Markdown')
    return ADDING_PHOTOS

async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, editing=False):

    ann_id = context.user_data.get('ann_id')

    if not ann_id:
        await update.message.reply_text("Ошибка: ID объявления не найден.")
        return CHOOSING

    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute(
            'SELECT description, price, username, photo_file_ids, message_ids, timestamp FROM announcements WHERE id = ?',
            (ann_id,))
        row = await cursor.fetchone()

        if not row:
            await update.message.reply_text("❌ Ошибка: объявление не найдено в базе.")
            return CHOOSING

        description, price, username, photo_file_ids, message_ids_json, timestamp = row
        photos = json.loads(photo_file_ids) if photo_file_ids else []
        message_ids = json.loads(message_ids_json) if message_ids_json else None

    is_updated = context.user_data.get('is_editing', False)

    # Формируем текст объявления
    message = await format_announcement_text(description, price, username, ann_id=ann_id,
                                             is_updated=is_updated, message_ids=message_ids, timestamp=timestamp)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝", callback_data=f'editdescription_{ann_id}'),
            InlineKeyboardButton("💰", callback_data=f'editprice_{ann_id}'),
            InlineKeyboardButton("🖼️", callback_data=f'editphotos_{ann_id}')
        ],
        [InlineKeyboardButton("📢 Опубликовать", callback_data=f'post_{ann_id}')]
    ])

    if photos:
        media = [InputMediaPhoto(photo_id, caption=message if idx == 0 else None, parse_mode='Markdown')
                 for idx, photo_id in enumerate(photos)]
        if update.message:
            await update.message.reply_media_group(media=media)
            await update.message.reply_text(PREVIEW_TEXT, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.callback_query.message.reply_media_group(media=media)
            await update.callback_query.message.reply_text(PREVIEW_TEXT, reply_markup=keyboard, parse_mode='Markdown')
    else:
        if update.message:
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.callback_query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

async def publish_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE, ann_id):
    """Публикация объявления в канал с обновлением timestamp и удалением старой версии."""
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT description, price, username, photo_file_ids, message_ids, timestamp FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()

        if not row:
            logger.error(f"Ошибка: объявление {ann_id} не найдено.")
            return None

        description, price, username, photo_file_ids, message_ids_json, timestamp = row
        photos = json.loads(photo_file_ids) if photo_file_ids else []
        old_message_ids = json.loads(message_ids_json) if message_ids_json else []

    is_updated = context.user_data.get('is_editing', False)
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Получаем текущее время

    # Удаляем старое объявление
    if old_message_ids:
        for message_id in old_message_ids:
            try:
                await context.bot.delete_message(chat_id=PRIVATE_CHANNEL_ID, message_id=message_id)
                logger.info(f"Удалено старое объявление {message_id} из канала.")
            except Exception as e:
                logger.error(f"Ошибка при удалении старого объявления {message_id}: {e}")

    message = await format_announcement_text(description, price, username, ann_id=ann_id, is_updated=is_updated, message_ids=old_message_ids, timestamp=current_timestamp)

    # Публикуем новое объявление
    if photos:
        media = [InputMediaPhoto(photo_id, caption=message if idx == 0 else None, parse_mode='Markdown') for idx, photo_id in enumerate(photos)]
        sent_messages = await context.bot.send_media_group(chat_id=PRIVATE_CHANNEL_ID, media=media)
        new_message_ids = [msg.message_id for msg in sent_messages]
    else:
        sent_message = await context.bot.send_message(chat_id=PRIVATE_CHANNEL_ID, text=message, parse_mode='Markdown')
        new_message_ids = [sent_message.message_id]

    # Обновляем запись в базе, включая `timestamp`
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('UPDATE announcements SET message_ids = ?, timestamp = ? WHERE id = ?',
                         (json.dumps(new_message_ids), current_timestamp, ann_id))
        await db.commit()

    return get_private_channel_post_link(PRIVATE_CHANNEL_ID, new_message_ids[0])

async def delete_announcement_by_id(ann_id, context, query):
    """Удаляет объявление из базы данных и, если опубликовано, удаляет его из канала."""
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()

        if row:
            message_ids_json = row[0]
            message_ids = json.loads(message_ids_json) if message_ids_json else []

            for message_id in message_ids:
                try:
                    await context.bot.delete_message(chat_id=PRIVATE_CHANNEL_ID, message_id=message_id)
                    logger.info(f"Удалено сообщение {message_id} из канала.")
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")

            await db.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
            await db.commit()
            logger.info(f"Объявление {ann_id} удалено из базы данных.")

            try:
                await query.message.delete()
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения пользователя: {e}")

async def show_user_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выводит список объявлений пользователя с кнопками для редактирования."""
    user_id = update.effective_user.id
    rows = await get_user_announcements(user_id)
    reply_message = update.effective_message

    if not rows:
        await reply_message.reply_text(NO_ANNOUNCEMENTS_MESSAGE, reply_markup=markup)
        return CHOOSING

    for row in rows:
        ann_id, message_ids_json, description, price, photo_file_ids_json = row
        message_ids = json.loads(message_ids_json) if message_ids_json else []
        photos = json.loads(photo_file_ids_json) if photo_file_ids_json else []

        status = "📝 *Черновик*\n\n" if not message_ids else f"📌 [Опубликовано]({get_private_channel_post_link(PRIVATE_CHANNEL_ID, message_ids[0])})\n\n"

        message = f"📌 *ID объявления:* {ann_id}\n\n{status}{ANNOUNCEMENT_LIST_MESSAGE.format(description=description, price=price)}"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📝", callback_data=f'editdescription_{ann_id}'),
                InlineKeyboardButton("💰", callback_data=f'editprice_{ann_id}'),
                InlineKeyboardButton("🖼️", callback_data=f'editphotos_{ann_id}'),
                InlineKeyboardButton("🔼", callback_data=f'up_{ann_id}'),
                InlineKeyboardButton("❌", callback_data=f'delete_{ann_id}')
            ],

        ])

        if photos:
            await reply_message.reply_photo(photo=photos[0], caption=message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await reply_message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

    return CHOOSING

async def format_announcement_text(description, price, username, ann_id=123, is_updated=False, message_ids=None,  timestamp=None):
    current_time = get_serbia_time()
    message = ""
    print(ann_id)
    message += f"📌 ID объявления: 3234235435345\n\n"
    message = f"{description}\n\n"
    message += f"{PRICE_TEXT}\n{price}\n\n"
    message += f"{CONTACT_TEXT}\n@{username.replace('_', '\_')}"

    if is_updated and message_ids:
        message += f"\n\n{UPDATED_TEXT.format(current_time=current_time)}"

    return message
