import telegram
from telegram import Update, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from datetime import datetime
from config import *
from keyboards import *
from utils import is_subscribed, show_menu, check_subscription_message, get_serbia_time
from texts import *  # Импортируем все тексты
from database import (
    save_announcement, get_user_announcements,
    delete_announcement_by_id as db_delete_announcement_by_id,
    has_user_ads, edit_announcement, update_announcement_description, get_announcement_for_edit,
    update_announcement_price
)
import json
import logging
from datetime import timedelta
import aiosqlite

from config import PRIVATE_CHANNEL_ID
from logger import logger

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await is_subscribed(user_id, context):
        text, keyboard = await check_subscription_message()
        await update.message.reply_text(text, reply_markup=keyboard)
        return CHECK_SUBSCRIPTION
    else:
        if await has_user_ads(user_id):
            await update.message.reply_text(WELCOME_NEW_USER, reply_markup=markup)
        else:
            await update.message.reply_text(WELCOME_NEW_USER, reply_markup=add_advertisement_keyboard)
        return CHOOSING


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if not await is_subscribed(user_id, context):
        text, keyboard = await check_subscription_message()
        await update.message.reply_text(text, reply_markup=keyboard)
        return CHECK_SUBSCRIPTION
    else:
        keyboard = [
            [InlineKeyboardButton(NEW_AD_CHOICE, callback_data='add_advertisement')],
            [InlineKeyboardButton(MY_ADS_CHOICE, callback_data='my_advertisements')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if await has_user_ads(user_id):
            await update.message.reply_text(WELCOME_NEW_USER, reply_markup=reply_markup)
        else:
            await update.message.reply_text(WELCOME_NEW_USER, reply_markup=reply_markup)
        return CHOOSING

async def format_announcement_text(description, price, username, is_updated=False):
    current_time = get_serbia_time()
    message = f"{description}\n\n"
    message += f"{PRICE_TEXT}\n{price}\n\n"
    message += f"{CONTACT_TEXT}\n@{username.replace('_', '\_')}"

    if is_updated:
        message += f"\n\n{UPDATED_TEXT.format(current_time=current_time)}"

    return message

async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Обработка кнопки "Новое хрустящее объявление"
    if query.data == 'add_advertisement':
        await handle_choice(update, context)

    # Обработка кнопки "Мои объявления"
    elif query.data == 'my_advertisements':
        await show_user_announcements(update, context)

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if await is_subscribed(user_id, context):
        await query.message.reply_text(SUBSCRIPTION_SUCCESS)
        await show_menu(query, context)
        return CHOOSING
    else:
        text, keyboard = await check_subscription_message()
        await query.message.reply_text(NOT_SUBSCRIBED_YET, reply_markup=keyboard)
        return

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == NEW_AD_CHOICE:
        context.user_data.clear()
        await update.message.reply_text(START_NEW_AD, reply_markup=ReplyKeyboardRemove())
        return DESCRIPTION
    elif choice == MY_ADS_CHOICE:
        await show_user_announcements(update, context)
        return CHOOSING
    else:
        await update.message.reply_text(CHOOSE_ACTION, reply_markup=markup)
        return CHOOSING

async def edit_photos_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photos'].append(photo.file_id)
        await update.message.reply_text(ADD_PHOTO_TEXT, reply_markup=finish_photo_markup_with_cancel)
    elif update.message.text == FINISH_PHOTO_UPLOAD:
        await send_preview(update, context, editing=True)
        return CONFIRMATION
    else:
        await update.message.reply_text(SEND_PHOTO_OR_FINISH)
    return ADDING_PHOTOS

async def remove_old_photos(old_message_ids, context):
    if old_message_ids:
        for message_id in old_message_ids:
            try:
                await context.bot.delete_message(chat_id=PRIVATE_CHANNEL_ID, message_id=message_id)
            except Exception as e:
                logger.error(f"{DELETE_OLD_MESSAGE_ERROR} {message_id}: {e}")

# Добавляем новую функцию для опубликованных объявлений
async def adding_photos_published(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"{ADDING_PHOTOS_STARTED_LOG} {update.effective_user.id}")

    if update.message.text == MAIN_MENU:
        await show_menu(update, context)
        return CHOOSING

    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        # Проверка на количество фотографий
        if len(context.user_data['photos']) < 10:
            photo = update.message.photo[-1]
            context.user_data['photos'].append(photo.file_id)
            logger.info(f"{PHOTO_ADDED_LOG} {photo.file_id}")

            # Отправляем сообщение один раз после загрузки первого фото
            if len(context.user_data['photos']) == 1:
                await update.message.reply_text(ADD_PHOTO_TEXT, reply_markup=finish_photo_markup_with_cancel)
        elif 'limit_reached' not in context.user_data:
            await update.message.reply_text(MAX_PHOTOS_REACHED)
            context.user_data['limit_reached'] = True

    elif update.message.text == FINISH_PHOTO_UPLOAD:
        logger.info(PHOTO_UPLOAD_FINISHED_LOG)

        await update.message.reply_text(PROCESSING_PHOTOS, reply_markup=ReplyKeyboardRemove())

        # Проверяем, есть ли описание и цена в контексте
        if not context.user_data.get('description') or not context.user_data.get('price'):
            ann_id = context.user_data.get('edit_ann_id')
            logger.info(f"{EDITING_AD_LOG} {ann_id}")

            async with aiosqlite.connect('announcements.db') as db:
                cursor = await db.execute('SELECT description, price FROM announcements WHERE id = ?', (ann_id,))
                row = await cursor.fetchone()
                if row:
                    context.user_data['description'], context.user_data['price'] = row
                    logger.info(f"{DESC_PRICE_FETCHED_LOG} {context.user_data['description']}, {context.user_data['price']}")
                else:
                    await update.message.reply_text(AD_NOT_FOUND)
                    return CHOOSING

        await send_preview(update, context, editing=True)
        return CONFIRMATION

    else:
        await update.message.reply_text(SEND_PHOTO_OR_FINISH)
    return ADDING_PHOTOS
# Добавляем новую функцию для неопубликованных объявлений
async def adding_photos_unpublished(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"{ADDING_PHOTOS_STARTED_LOG} {update.effective_user.id}")

    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        if len(context.user_data['photos']) < 10:
            photo = update.message.photo[-1]
            context.user_data['photos'].append(photo.file_id)
            logger.info(f"{PHOTO_ADDED_LOG} {photo.file_id}")

            if len(context.user_data['photos']) == 1:
                await update.message.reply_text(ADD_PHOTO_TEXT, reply_markup=finish_photo_markup_with_cancel)
        elif 'limit_reached' not in context.user_data:
            await update.message.reply_text(MAX_PHOTOS_REACHED)
            context.user_data['limit_reached'] = True

    elif update.message.text in [NO_PHOTO_AD, FINISH_PHOTO_UPLOAD]:
        await update.message.reply_text(PROCESSING_PHOTOS, reply_markup=ReplyKeyboardRemove())

        if not context.user_data.get('description') or not context.user_data.get('price'):
            await update.message.reply_text(DESC_PRICE_REQUIRED)
            return ADDING_PHOTOS

        # Сохраняем состояние без публикации, убирая отметку "обновлено"
        await edit_unpublished_announcement(update, context)
        return CONFIRMATION

    else:
        await update.message.reply_text(SEND_PHOTO_OR_FINISH_OR_NO_PHOTO)

    return ADDING_PHOTOS

async def handle_add_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Определяет, какое объявление редактируется — опубликованное или неопубликованное, и вызывает соответствующую функцию."""
    if 'edit_ann_id' in context.user_data:
        return await adding_photos_published(update, context)
    else:
        return await adding_photos_unpublished(update, context)

async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    description = update.message.text.strip()

    # Проверка на количество символов (4096 символов для описания)
    if len(description) > 4096:
        await update.message.reply_text(f'❗Описание слишком длинное. Максимум 4096 символов. Сейчас: {len(description)} символов.')
        return DESCRIPTION

    # Проверяем, что описание не пустое
    if not description:
        await update.message.reply_text('❗Описание не может быть пустым. Пожалуйста, введите описание.')
        return DESCRIPTION

    context.user_data['description'] = description
    await update.message.reply_text('Принято! Теперь укажите цену. ')  # Убираем кнопку "В главное меню"
    return PRICE

async def price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = update.message.text.strip()

    if len(price) > 255:
        await update.message.reply_text(LONG_PRICE_ERROR.format(len(price)))
        return PRICE

    if not price:
        await update.message.reply_text(EMPTY_PRICE_ERROR)
        return PRICE

    context.user_data['price'] = price
    await update.message.reply_text(ASK_FOR_PHOTOS, reply_markup=photo_markup_with_cancel, parse_mode='Markdown')
    context.user_data['photos'] = []
    return ADDING_PHOTOS

async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, editing=None, is_published=True):
    description = context.user_data.get('new_description', context.user_data.get('description'))
    price = context.user_data.get('new_price', context.user_data.get('price'))
    photos = context.user_data.get('photos', [])

    user = update.message.from_user if update.message else update.callback_query.from_user
    username = user.username if user.username else user.first_name
    context.user_data['username'] = username

    is_updated = editing and is_published
    message = await format_announcement_text(description, price, username, is_updated=is_updated)

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

async def confirm_edit_unpublished(context):
    logger.info("Начало функции confirm_edit_unpublished")

    description = context.user_data.get('new_description', context.user_data.get('description'))
    price = context.user_data.get('new_price', context.user_data.get('price'))
    photos = context.user_data.get('photos', [])
    username = context.user_data.get('username')

    # Формируем текст объявления
    message_text = await format_announcement_text(description, price, username)

    if photos:
        media = []
        for idx, photo_id in enumerate(photos):
            if idx == 0:
                media.append(InputMediaPhoto(media=photo_id, caption=message_text, parse_mode='Markdown'))
            else:
                media.append(InputMediaPhoto(media=photo_id))

        sent_messages = await context.bot.send_media_group(chat_id=PRIVATE_CHANNEL_ID, media=media)
        message_ids = [msg.message_id for msg in sent_messages]
        logger.info(f"Фотографии отправлены, новые message_ids: {message_ids}")
    else:
        sent_message = await context.bot.send_message(chat_id=PRIVATE_CHANNEL_ID, text=message_text, parse_mode='Markdown')
        message_ids = [sent_message.message_id]
        logger.info(f"Отправлено текстовое сообщение, message_id: {message_ids[0]}")

    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('''
            INSERT INTO announcements (user_id, username, message_ids, description, price, photo_file_ids)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            context.user_data['user_id'],
            username,
            json.dumps(message_ids),
            description,
            price,
            json.dumps(photos)
        ))
        ann_id = cursor.lastrowid
        await db.commit()

    context.user_data['edit_ann_id'] = ann_id

    # Формируем ссылку на пост в приватном канале
    post_link = f"https://t.me/c/{str(PRIVATE_CHANNEL_ID)[4:]}/{message_ids[0]}"
    logger.info(f"Ссылка на новое объявление: {post_link}")

    return post_link


async def confirm_edit_published(context, update, ann_id):
    logger.info(f"Начало функции confirm_edit_published для объявления ID: {ann_id}")

    description = context.user_data.get('new_description', context.user_data.get('description'))
    price = context.user_data.get('new_price', context.user_data.get('price'))
    photos = context.user_data.get('photos', [])
    username = context.user_data.get('username')

    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()

        if row:
            old_message_ids = json.loads(row[0])
            await remove_old_photos(old_message_ids, context)

            message_text = await format_announcement_text(description, price, username, is_updated=True)

            if photos:
                media = []
                for idx, photo_id in enumerate(photos):
                    if idx == 0:
                        media.append(InputMediaPhoto(media=photo_id, caption=message_text, parse_mode='Markdown'))
                    else:
                        media.append(InputMediaPhoto(media=photo_id))

                sent_messages = await context.bot.send_media_group(chat_id=PRIVATE_CHANNEL_ID, media=media)
                new_message_ids = [msg.message_id for msg in sent_messages]
                logger.info(f"Новые фотографии отправлены, новые message_ids: {new_message_ids}")
            else:
                sent_message = await context.bot.send_message(chat_id=PRIVATE_CHANNEL_ID, text=message_text, parse_mode='Markdown')
                new_message_ids = [sent_message.message_id]
                logger.info(f"Отправлено текстовое сообщение, message_id: {new_message_ids[0]}")

            await db.execute('''
                UPDATE announcements
                SET description = ?, price = ?, message_ids = ?, photo_file_ids = ?
                WHERE id = ?
            ''', (
                description, price, json.dumps(new_message_ids), json.dumps(photos), ann_id
            ))
            await db.commit()

            post_link = f"https://t.me/c/{str(PRIVATE_CHANNEL_ID)[4:]}/{new_message_ids[0]}"
            logger.info(f"Ссылка на обновленное объявление: {post_link}")

            return post_link
        else:
            logger.error(AD_NOT_FOUND_ERROR.format(ann_id))
            return None

async def edit_unpublished_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Функция для редактирования неопубликованных объявлений."""
    description = context.user_data.get('new_description', context.user_data.get('description'))
    price = context.user_data.get('new_price', context.user_data.get('price'))
    photos = context.user_data.get('photos', [])

    # Формирование предварительного просмотра без отметки об обновлении
    user = update.message.from_user if update.message else update.callback_query.from_user
    username = user.username if user.username else user.first_name
    context.user_data['username'] = username

    # Формируем текст без отметки "обновлено"
    message = await format_announcement_text(description, price, username, is_updated=False)

    # Отправляем новый предварительный просмотр
    if update.message and update.message.reply_markup:
        await update.message.reply_text(PREVIEW_LOADING, reply_markup=ReplyKeyboardRemove())

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

    return CONFIRMATION

async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    logger.info(CONFIRMATION_HANDLER_LOG.format(data))

    if data == 'preview_edit':
        await query.message.reply_text(EDIT_PROMPT, reply_markup=edit_markup_with_cancel)
        return EDIT_CHOICE

    elif data == 'post':
        logger.info(USER_POST_CHOICE)

        # Если нет user_id в контексте, устанавливаем его
        if 'user_id' not in context.user_data:
            context.user_data['user_id'] = query.from_user.id  # Получаем ID пользователя из callback запроса

        # Проверим, опубликованное ли это объявление или нет
        ann_id = context.user_data.get('edit_ann_id')

        if ann_id:
            logger.info(EDIT_ANNOUNCEMENT_LOG.format(ann_id))
            post_link = await confirm_edit_published(context, update, ann_id)
        else:
            logger.info(NEW_ANNOUNCEMENT_LOG)
            post_link = await confirm_edit_unpublished(context)

        if post_link:
            await query.message.reply_text(POST_SUCCESS_MESSAGE.format(post_link), reply_markup=markup, parse_mode='Markdown')
        else:
            await query.message.reply_text(POST_FAILURE_MESSAGE, reply_markup=markup)
        return CHOOSING

async def edit_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Удаляем текущее сообщение, если оно существует
    try:
        await query.message.delete()
    except telegram.error.BadRequest:
        pass  # Игнорируем ошибку, если сообщение не найдено

    if data == 'edit_description':
        context.user_data.pop('new_description', None)
        await query.message.reply_text(EDIT_DESCRIPTION_PROMPT, reply_markup=ReplyKeyboardRemove())
        return EDIT_DESCRIPTION

    elif data == 'edit_price':
        context.user_data.pop('new_price', None)
        await query.message.reply_text(EDIT_PRICE_PROMPT, reply_markup=ReplyKeyboardRemove())
        return EDIT_PRICE

    elif data == 'edit_photos':
        if 'edit_ann_id' not in context.user_data:
            context.user_data['edit_ann_id'] = context.user_data.get('current_ann_id')
        context.user_data['edit_photos'] = True
        context.user_data['photos'] = []

        await query.message.reply_text(EDIT_PHOTOS_PROMPT, reply_markup=finish_photo_markup_with_cancel)
        return ADDING_PHOTOS

    elif data == 'cancel_edit':
        if 'edit_ann_id' not in context.user_data:
            # Для неопубликованных объявлений оставляем предварительный просмотр
            is_editing = 'edit_ann_id' in context.user_data
            await send_preview(update, context, editing=is_editing)
            return CONFIRMATION
        else:
            # Для опубликованных объявлений возвращаемся в состояние CHOOSING
            return CHOOSING

async def edit_description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_description = update.message.text.strip()

    if not new_description:
        await update.message.reply_text(EMPTY_DESCRIPTION_ERROR)
        return EDIT_DESCRIPTION

    context.user_data['new_description'] = new_description

    if 'edit_ann_id' not in context.user_data:
        # Обновление данных для неопубликованного объявления
        await edit_unpublished_announcement(update, context)
        return CONFIRMATION
    else:
        # Обработка для опубликованного объявления
        ann_id = context.user_data['edit_ann_id']

        async with aiosqlite.connect('announcements.db') as db:
            cursor = await db.execute('SELECT price, photo_file_ids FROM announcements WHERE id = ?', (ann_id,))
            row = await cursor.fetchone()
            if row:
                current_price, photo_file_ids = row
                photos = json.loads(photo_file_ids) if photo_file_ids else []
                context.user_data['photos'] = photos
                context.user_data['price'] = current_price

                await db.execute('UPDATE announcements SET description = ? WHERE id = ?', (new_description, ann_id))
                await db.commit()

                await send_preview(update, context, editing=True, is_published=True)
                return CONFIRMATION
            else:
                await update.message.reply_text(ANNOUNCEMENT_NOT_FOUND)
                return CHOOSING

async def edit_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод новой цены для редактирования объявления.
    """
    new_price = update.message.text.strip()

    # Проверка на пустую цену
    if not new_price:
        await update.message.reply_text(EMPTY_PRICE_ERROR)
        return CHOOSING

    context.user_data['new_price'] = new_price

    # Если это существующее объявление, обновляем его в базе данных
    if 'edit_ann_id' in context.user_data:
        ann_id = context.user_data['edit_ann_id']

        # Получаем текущие данные объявления из базы
        announcement = await get_announcement_for_edit(ann_id)
        if announcement:
            # Обновляем только цену
            await update_announcement_price(ann_id, new_price)
            await send_preview(update, context, editing=True)
            return CONFIRMATION
        else:
            await update.message.reply_text(ANNOUNCEMENT_NOT_FOUND)
            return CHOOSING
    else:
        # Обрабатываем для нового объявления
        await send_preview(update, context, editing=False, is_published=False)
        return CONFIRMATION

async def check_relevance(context: ContextTypes.DEFAULT_TYPE):
    user_data = context.job.data
    user_id = user_data['user_id']
    message_id = user_data['message_id']

    # Отправляем пользователю сообщение с вопросом о продлении или удалении объявления
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(EXTEND_BUTTON, callback_data=f'extend_{message_id}'),
         InlineKeyboardButton(REMOVE_BUTTON, callback_data=f'remove_{message_id}')]
    ])
    try:
        await context.bot.send_message(chat_id=user_id, text=RELEVANCE_CHECK_MESSAGE, reply_markup=keyboard)
    except Exception as e:
        logger.error(SEND_MESSAGE_ERROR.format(e))

async def delete_announcement_by_message_id(message_id, context: ContextTypes.DEFAULT_TYPE):
    # Удаляем сообщение из канала
    try:
        await context.bot.delete_message(chat_id=PRIVATE_CHANNEL_ID, message_id=message_id)
    except Exception as e:
        logger.error(DELETE_MESSAGE_ERROR.format(e))

    # Удаляем запись из базы данных
    async with aiosqlite.connect('announcements.db') as db:
        await db.execute('DELETE FROM announcements WHERE message_id = ?', (message_id,))
        await db.commit()

async def relevance_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith('extend_'):
        message_id = int(data.split('_')[1])
        context.job_queue.run_once(check_relevance, when=timedelta(weeks=2), data={'user_id': query.from_user.id, 'message_id': message_id})
        await query.message.reply_text(EXTENDED_MESSAGE)
    elif data.startswith('remove_'):
        message_id = int(data.split('_')[1])
        # Удаляем объявление из канала и базы данных
        await delete_announcement_by_message_id(message_id, context)
        # await query.message.reply_text(DELETE_SUCCESS_MESSAGE)

async def send_announcement(context: ContextTypes.DEFAULT_TYPE, update: Update):
    channel_id = PRIVATE_CHANNEL_ID
    photos = context.user_data.get('photos', [])
    description = context.user_data['description']
    price = context.user_data['price']

    # Получаем username или first_name для автора объявления
    user = update.callback_query.from_user if update.callback_query else update.message.from_user
    username = user.username if user.username else user.first_name
    context.user_data['username'] = username

    # Формируем сообщение
    message = ANNOUNCEMENT_MESSAGE.format(username=username, description=description, price=price)

    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH]

    if photos:
        media = []
        for idx, photo_id in enumerate(photos):
            if idx == 0:
                # Добавляем автора и описание в первое фото
                media.append(InputMediaPhoto(media=photo_id, caption=message))
            else:
                media.append(InputMediaPhoto(media=photo_id))
        sent_messages = await context.bot.send_media_group(chat_id=channel_id, media=media)
        message_ids = [msg.message_id for msg in sent_messages]
    else:
        sent_message = await context.bot.send_message(chat_id=channel_id, text=message)
        message_ids = [sent_message.message_id]

    # Сохраняем объявление в базе данных
    await save_announcement(
        user_id=user.id,
        username=username,
        message_ids=message_ids,
        description=description,
        price=price,
        photos=photos
    )

    # Планируем проверку через 2 недели (опционально)
    context.job_queue.run_once(
        check_relevance,
        when=timedelta(weeks=2),
        data=context.user_data.copy()
    )

    # Создаем ссылку на объявление
    post_link = get_private_channel_post_link(PRIVATE_CHANNEL_ID, message_ids[0])

    return post_link

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith('edit_'):
        ann_id = int(data.split('_')[1])
        context.user_data['edit_ann_id'] = ann_id
        context.user_data['is_editing'] = True
        context.user_data.pop('new_description', None)
        context.user_data.pop('new_price', None)
        await query.message.reply_text(EDIT_PROMPT, reply_markup=edit_markup_with_cancel)
        return EDIT_CHOICE
    elif data.startswith('delete_'):
        ann_id = int(data.split('_')[1])
        await delete_announcement_by_id(ann_id, context, query)
        # await query.message.reply_text(DELETE_SUCCESS_MESSAGE)
        return CHOOSING
    else:
        # Обработка других callback данных, если необходимо
        pass

    return CHOOSING

async def delete_announcement_by_id(ann_id, context, query):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids, photo_file_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if row:
            message_ids = json.loads(row[0])
            photos = json.loads(row[1]) if row[1] else []

            for message_id in message_ids:
                try:
                    await context.bot.delete_message(chat_id=PRIVATE_CHANNEL_ID, message_id=message_id)
                    logger.info(DELETE_SUCCESS_LOG.format(message_id))
                except Exception as e:
                    logger.error(DELETE_ERROR_LOG.format(message_id, e))

            # Удаляем запись об объявлении из базы данных
            await db.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
            await db.commit()

            try:
                await query.message.delete()
                logger.info(USER_MESSAGE_DELETE_LOG)
            except Exception as e:
                logger.error(USER_MESSAGE_DELETE_ERROR_LOG.format(e))

async def show_user_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = await get_user_announcements(user_id)
    reply_message = update.effective_message

    if not rows:
        await reply_message.reply_text(NO_ANNOUNCEMENTS_MESSAGE, reply_markup=markup)
        return CHOOSING

    for row in rows:
        ann_id, message_ids_json, description, price, photo_file_ids_json = row
        message_ids = json.loads(message_ids_json)
        photos = json.loads(photo_file_ids_json) if photo_file_ids_json else []

        message = ANNOUNCEMENT_LIST_MESSAGE.format(description=description, price=price)
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH]

        # Добавляем ссылку на объявление в канале
        post_link = get_private_channel_post_link(PRIVATE_CHANNEL_ID, message_ids[0])
        message += f"\n\n[{FULL_VERSION_MESSAGE}]({post_link})"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(EDIT, callback_data=f'edit_{ann_id}'),
                InlineKeyboardButton(DELETE_BUTTON, callback_data=f'delete_{ann_id}')
            ]
        ])

        if photos:
            await reply_message.reply_photo(photo=photos[0], caption=message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await reply_message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

    return CHOOSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(CANCEL_MESSAGE, reply_markup=markup)
    return CHOOSING

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(ERROR_LOG, exc_info=context.error)

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_type = chat.type
    chat_id = chat.id

    if chat_type in ['group', 'supergroup', 'channel']:
        await update.message.reply_text(f"Chat ID этого {chat_type}: `{chat_id}`", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"Ваш личный Chat ID: `{chat_id}`", parse_mode='Markdown')

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await is_subscribed(user_id, context):
        await query.message.reply_text(SUBSCRIPTION_SUCCESS)
        await show_menu(update, context)
        return CHOOSING
    else:
        text, keyboard = await check_subscription_message()
        await query.message.reply_text("Вы еще не подписаны на канал.", reply_markup=keyboard)
        return CHECK_SUBSCRIPTION



def get_private_channel_post_link(channel_id, message_id):
    channel_id_str = str(channel_id)
    if channel_id_str.startswith('-100'):
        channel_id_str = channel_id_str[4:]
    return f"https://t.me/c/{channel_id_str}/{message_id}"