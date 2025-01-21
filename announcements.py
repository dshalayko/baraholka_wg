import json
import logging
import aiosqlite
from datetime import timedelta
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
        await update.message.reply_text("Ошибка: ID объявления не найден.")
        return CHOOSING

    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        if len(context.user_data['photos']) < 10:
            photo = update.message.photo[-1]
            context.user_data['photos'].append(photo.file_id)
            logger.info(f"Добавлено фото: {photo.file_id}")

            async with aiosqlite.connect('announcements.db') as db:
                await db.execute('UPDATE announcements SET photo_file_ids = ? WHERE id = ?',
                                 (json.dumps(context.user_data['photos']), ann_id))
                await db.commit()

            if len(context.user_data['photos']) == 1:
                await update.message.reply_text(ADD_PHOTO_TEXT, reply_markup=finish_photo_markup_with_cancel)
        else:
            await update.message.reply_text(MAX_PHOTOS_REACHED)

    elif update.message.text in [NO_PHOTO_AD, FINISH_PHOTO_UPLOAD]:
        await update.message.reply_text(PROCESSING_PHOTOS, reply_markup=ReplyKeyboardRemove())

        if not context.user_data.get('description') or not context.user_data.get('price'):
            await update.message.reply_text(DESC_PRICE_REQUIRED)
            return ADDING_PHOTOS

        await send_preview(update, context)
        return CONFIRMATION

    else:
        await update.message.reply_text(SEND_PHOTO_OR_FINISH_OR_NO_PHOTO)

    return ADDING_PHOTOS

async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение и обновление описания объявления в БД."""
    ann_id = context.user_data.get('ann_id')

    if not ann_id:
        await update.message.reply_text("Ошибка: ID объявления не найден.")
        return CHOOSING

    description = update.message.text.strip()

    if len(description) > 4096:
        await update.message.reply_text(f'❗Описание слишком длинное. Максимум 4096 символов. Сейчас: {len(description)} символов.')
        return EDIT_DESCRIPTION

    if not description:
        await update.message.reply_text('❗Описание не может быть пустым. Пожалуйста, введите описание.')
        return EDIT_DESCRIPTION

    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('UPDATE announcements SET description = ? WHERE id = ?', (description, ann_id))
        await db.commit()

    context.user_data['description'] = description

    # Если это редактирование, сразу показываем предпросмотр
    if context.user_data.get('is_editing'):
        await send_preview(update, context, editing=True)
        return CONFIRMATION

    # Если это создание объявления, продолжаем процесс
    await update.message.reply_text('Принято! Теперь укажите цену.')
    return PRICE

async def price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение и обновление цены объявления в БД."""
    ann_id = context.user_data.get('ann_id')

    if not ann_id:
        await update.message.reply_text("Ошибка: ID объявления не найден.")
        return CHOOSING

    price = update.message.text.strip()

    if len(price) > 255:
        await update.message.reply_text(LONG_PRICE_ERROR.format(len(price)))
        return EDIT_PRICE

    if not price:
        await update.message.reply_text(EMPTY_PRICE_ERROR)
        return EDIT_PRICE

    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('UPDATE announcements SET price = ? WHERE id = ?', (price, ann_id))
        await db.commit()

    context.user_data['price'] = price

    # Если это редактирование, сразу показываем предпросмотр
    if context.user_data.get('is_editing'):
        await send_preview(update, context, editing=True)
        return CONFIRMATION

    # Если это создание объявления, продолжаем процесс
    await update.message.reply_text(ASK_FOR_PHOTOS, reply_markup=photo_markup_with_cancel, parse_mode='Markdown')
    return ADDING_PHOTOS

async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, editing=False):
    """Формирует и отправляет предпросмотр объявления с ID."""
    ann_id = context.user_data.get('ann_id')
    description = context.user_data.get('description', '')
    price = context.user_data.get('price', '')
    photos = context.user_data.get('photos', [])
    username = context.user_data.get('username', '')

    # Формируем текст объявления
    message = await format_announcement_text(description, price, username, ann_id=ann_id, is_updated=editing)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(EDIT, callback_data='preview_edit')],
        [InlineKeyboardButton(POST, callback_data='post')]
    ])

    if photos:
        media = [InputMediaPhoto(photo_id, caption=message if idx == 0 else None, parse_mode='Markdown')
                 for idx, photo_id in enumerate(photos)]
        if update.message:
            await update.message.reply_media_group(media=media)
            await update.message.reply_text(PREVIEW_TEXT, reply_markup=keyboard)
        else:
            await update.callback_query.message.reply_media_group(media=media)
            await update.callback_query.message.reply_text(PREVIEW_TEXT, reply_markup=keyboard)
    else:
        if update.message:
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.callback_query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

async def publish_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE, ann_id):
    """Публикация объявления в канал и обновление записи в БД."""
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT description, price, username, photo_file_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()

        if not row:
            logger.error(f"Ошибка: объявление {ann_id} не найдено.")
            return None

        description, price, username, photo_file_ids = row
        photos = json.loads(photo_file_ids) if photo_file_ids else []

    # Формируем сообщение с ID объявления
    message = await format_announcement_text(description, price, username, ann_id=ann_id)

    # Отправляем объявление в канал
    if photos:
        media = [InputMediaPhoto(photo_id, caption=message if idx == 0 else None, parse_mode='Markdown') for idx, photo_id in enumerate(photos)]
        sent_messages = await context.bot.send_media_group(chat_id=PRIVATE_CHANNEL_ID, media=media)
        message_ids = [msg.message_id for msg in sent_messages]
    else:
        sent_message = await context.bot.send_message(chat_id=PRIVATE_CHANNEL_ID, text=message, parse_mode='Markdown')
        message_ids = [sent_message.message_id]

    # Обновляем запись в базе, добавляя message_id
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('UPDATE announcements SET message_ids = ? WHERE id = ?', (json.dumps(message_ids), ann_id))
        await db.commit()

    return get_private_channel_post_link(PRIVATE_CHANNEL_ID, message_ids[0])

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
    """Выводит список объявлений пользователя, включая статус (черновик или опубликовано)."""
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
        message = f"{status}{ANNOUNCEMENT_LIST_MESSAGE.format(description=description, price=price)}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(EDIT, callback_data=f'edit_{ann_id}'),
             InlineKeyboardButton(DELETE_BUTTON, callback_data=f'delete_{ann_id}')]
        ])

        if photos:
            await reply_message.reply_photo(photo=photos[0], caption=message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await reply_message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

    return CHOOSING

async def format_announcement_text(description, price, username, ann_id=None, is_updated=False):
    current_time = get_serbia_time()
    message = ""
    if ann_id:
        message += f"📌 ID объявления: {ann_id}\n\n"
    message = f"{description}\n\n"
    message += f"{PRICE_TEXT}\n{price}\n\n"
    message += f"{CONTACT_TEXT}\n@{username.replace('_', '\_')}"

    if is_updated:
        message += f"\n\n{UPDATED_TEXT.format(current_time=current_time)}"

    return message
