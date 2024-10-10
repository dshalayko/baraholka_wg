from telegram import Update, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from config import *
from keyboards import *
from utils import is_subscribed, show_menu, check_subscription_message
from database import (
    save_announcement, get_user_announcements,
    delete_announcement_by_id as db_delete_announcement_by_id,
    update_announcement, has_user_ads, edit_announcement
)
import json
import logging
from datetime import timedelta
import aiosqlite

from config import CHANNEL_USERNAME
from logger import logger  # Импорт логгера


logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await is_subscribed(user_id, context):
        text, keyboard = await check_subscription_message()
        await update.message.reply_text(text, reply_markup=keyboard)
        return CHECK_SUBSCRIPTION
    else:
        # Проверяем, есть ли у пользователя объявления
        if await has_user_ads(user_id):
            # Существующий пользователь: показываем меню с двумя кнопками
            await update.message.reply_text(
                'Добро пожаловать! Выберите действие:',
                reply_markup=markup  # Клавиатура с двумя кнопками
            )
        else:
            # Новый пользователь: показываем только кнопку «Добавить объявление»
            await update.message.reply_text(
                'Добро пожаловать! Вы можете добавить свое первое объявление.',
                reply_markup=add_advertisement_keyboard  # Клавиатура с одной кнопкой
            )
        return CHOOSING

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await is_subscribed(user_id, context):
        text, keyboard = await check_subscription_message()
        await update.message.reply_text(text, reply_markup=keyboard)
        return CHECK_SUBSCRIPTION
    else:
        # Проверяем, есть ли у пользователя объявления
        if await has_user_ads(user_id):
            # Существующий пользователь: показываем меню с двумя кнопками
            await update.message.reply_text(
                'Выберите действие:',
                reply_markup=markup  # Клавиатура с двумя кнопками
            )
        else:
            # Новый пользователь: показываем только кнопку «Добавить объявление»
            await update.message.reply_text(
                'Вы можете добавить свое первое объявление.',
                reply_markup=add_advertisement_keyboard  # Клавиатура с одной кнопкой
            )
        return CHOOSING

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if await is_subscribed(user_id, context):
        await query.message.reply_text(
            'Спасибо за подписку!',
        )
        await show_menu(query, context)
        return CHOOSING
    else:
        text, keyboard = await check_subscription_message()
        await query.message.reply_text('Вы еще не подписались на канал. Пожалуйста, подпишитесь и нажмите "Я подписался".', reply_markup=keyboard)
        return

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == 'Добавить объявление':
        # Очищаем все данные пользователя
        context.user_data.clear()
        await update.message.reply_text('Пожалуйста, отправьте описание вашего объявления.', reply_markup=cancel_markup)
        return DESCRIPTION
    elif choice == 'Мои объявления':
        await show_user_announcements(update, context)
        return CHOOSING  # Возвращаемся в состояние CHOOSING после показа объявлений
    else:
        await update.message.reply_text('Пожалуйста, выберите действие с помощью кнопок.', reply_markup=markup)
        return CHOOSING

async def edit_photos_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photos'].append(photo.file_id)
        await update.message.reply_text('Фото добавлено. Вы можете отправить еще одно или нажать "Закончить загрузку фото".',
                                        reply_markup=finish_photo_markup_with_cancel)
    elif update.message.text == 'Закончить загрузку фото':
        # Переходим к предварительному просмотру после завершения загрузки фотографий
        await send_preview(update, context, editing=True)
        return CONFIRMATION
    else:
        await update.message.reply_text('Пожалуйста, отправьте фотографию или нажмите "Закончить загрузку фото".')
    return ADDING_PHOTOS

async def remove_old_photos(old_message_ids, context):
    """
    Removes old photos/messages from the Telegram channel.
    :param old_message_ids: List of message IDs to be deleted from the channel.
    :param context: Context of the current bot interaction.
    """
    if old_message_ids:
        for message_id in old_message_ids:
            try:
                await context.bot.delete_message(chat_id=CHANNEL_USERNAME, message_id=message_id)
            except Exception as e:
                logger.error(f"Ошибка при удалении старого сообщения {message_id}: {e}")

async def adding_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    text = update.message.text

    if text == 'Объявление без фото':
        if not context.user_data.get('description') or not context.user_data.get('price'):
            await update.message.reply_text('Описание и цена обязательны для создания объявления.')
            return ADDING_PHOTOS

        await send_preview(update, context)
        return CONFIRMATION

    elif text == 'Закончить загрузку фото' or text == '/done':
        if not context.user_data.get('description') or not context.user_data.get('price'):
            await update.message.reply_text('Описание и цена обязательны для создания объявления.')
            return ADDING_PHOTOS

        if not context.user_data['photos'] and not context.user_data.get('edit_photos'):
            await update.message.reply_text(
                'Вы не добавили ни одной фотографии. Пожалуйста, отправьте хотя бы одну фотографию или нажмите "Объявление без фото".'
            )
            return ADDING_PHOTOS

        # Handle new announcement or edited photos
        if context.user_data.get('edit_photos'):
            ann_id = context.user_data.get('edit_ann_id')
            if ann_id:
                # Handle editing photos for an existing announcement
                async with aiosqlite.connect('announcements.db') as db:
                    cursor = await db.execute('SELECT description, price, message_ids FROM announcements WHERE id = ?', (ann_id,))
                    row = await cursor.fetchone()
                    if row:
                        description, price, old_message_ids = row
                        context.user_data['description'] = description
                        context.user_data['price'] = price

                        # Remove old photos and show preview with new photos
                        await remove_old_photos(old_message_ids, context)
                        context.user_data.pop('edit_photos', None)
                        await send_preview(update, context, editing=True)
                        return CONFIRMATION
                    else:
                        await update.message.reply_text('Не удалось найти объявление для редактирования.')
                        return CHOOSING
            else:
                # New announcement scenario
                context.user_data.pop('edit_photos', None)
                await send_preview(update, context)
                return CONFIRMATION
        else:
            # Handle new photo upload scenario
            await send_preview(update, context)
            return CONFIRMATION

    elif text == 'Вернуться в меню':
        await show_menu(update, context)
        return CHOOSING

    elif update.message.photo:
        # Append new photos to context
        photo = update.message.photo[-1]
        context.user_data['photos'].append(photo.file_id)
        await update.message.reply_text(
            'Фото добавлено. Вы можете отправить еще одно или нажать "Закончить загрузку фото".',
            reply_markup=finish_photo_markup_with_cancel
        )
        return ADDING_PHOTOS
    else:
        await update.message.reply_text(
            'Пожалуйста, отправьте фотографию, нажмите "Закончить загрузку фото", "Объявление без фото" или "Вернуться в меню".'
        )
        return ADDING_PHOTOS

async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'Вернуться в меню':
        await show_menu(update, context)
        return CHOOSING

    description = update.message.text.strip()
    if not description:
        await update.message.reply_text('Описание не может быть пустым. Пожалуйста, введите описание.')
        return DESCRIPTION

    context.user_data['description'] = description
    await update.message.reply_text('Теперь укажите цену.', reply_markup=cancel_markup)
    return PRICE

async def price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'Вернуться в меню':
        await show_menu(update, context)
        return CHOOSING

    price = update.message.text.strip()
    if not price:
        await update.message.reply_text('Цена не может быть пустой. Пожалуйста, введите цену.')
        return PRICE

    context.user_data['price'] = price
    await update.message.reply_text(
        'Теперь отправьте фото вашего объявления. Вы можете отправить несколько фотографий по очереди.\n'
        'Когда закончите, нажмите кнопку "Закончить загрузку фото" или отправьте команду /done.\n'
        'Если хотите создать объявление без фото, нажмите кнопку ниже.',
        reply_markup=photo_markup_with_cancel
    )
    context.user_data['photos'] = []
    return ADDING_PHOTOS


async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, editing=None):
    # Используем новые значения описания и цены, если они были предоставлены
    description = context.user_data.get('new_description', context.user_data.get('description'))
    price = context.user_data.get('new_price', context.user_data.get('price'))
    photos = context.user_data.get('photos', [])

    # Получаем username или first_name из контекста
    user = update.message.from_user if update.message else update.callback_query.from_user
    username = user.username if user.username else user.first_name
    context.user_data['username'] = username  # Сохраняем username в context.user_data

    message = f"Автор: @{username}\nОписание: {description}\nЦена: {price}"

    if editing:
        message += "\n\nОбновлено"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('Редактировать', callback_data='preview_edit')],
            [InlineKeyboardButton('Подтвердить изменения', callback_data='confirm_edit')]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('Редактировать', callback_data='preview_edit')],
            [InlineKeyboardButton('Разместить объявление', callback_data='post')]
        ])

    # Отправляем фотографии или текст
    if photos:
        media = []
        for idx, photo_id in enumerate(photos):
            if idx == 0:
                media.append(InputMediaPhoto(media=photo_id, caption=message))
            else:
                media.append(InputMediaPhoto(media=photo_id))

        if update.message:
            await update.message.reply_media_group(media=media)
            await update.message.reply_text('Предварительный просмотр:', reply_markup=keyboard)
        else:
            await update.callback_query.message.reply_media_group(media=media)
            await update.callback_query.message.reply_text('Предварительный просмотр:', reply_markup=keyboard)
    else:
        if update.message:
            await update.message.reply_text(message, reply_markup=keyboard)
        else:
            await update.callback_query.message.reply_text(message, reply_markup=keyboard)

async def confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ann_id = context.user_data.get('edit_ann_id')
    if ann_id:
        description = context.user_data.get('new_description', context.user_data.get('description'))
        price = context.user_data.get('new_price', context.user_data.get('price'))
        photos = context.user_data.get('photos', [])  # Updated photos

        # Get old message IDs for deletion
        async with aiosqlite.connect('announcements.db') as db:
            cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
            row = await cursor.fetchone()
            if row:
                old_message_ids = json.loads(row[0])

                # Delete old messages
                for message_id in old_message_ids:
                    try:
                        await context.bot.delete_message(chat_id=CHANNEL_USERNAME, message_id=message_id)
                    except Exception as e:
                        logger.error(f"Error deleting old message {message_id}: {e}")

                # Prepare and send the updated advertisement
                message_text = f"Описание: {description}\nЦена: {price}\n\nОбновлено"
                new_message_ids = []

                # If there are photos, send the updated photo set
                if photos:
                    media = []
                    for idx, photo_id in enumerate(photos):
                        if idx == 0:
                            media.append(InputMediaPhoto(media=photo_id, caption=message_text))
                        else:
                            media.append(InputMediaPhoto(media=photo_id))

                    # Send new media group
                    sent_messages = await context.bot.send_media_group(chat_id=CHANNEL_USERNAME, media=media)
                    new_message_ids = [msg.message_id for msg in sent_messages]
                else:
                    # Send text if no photos are provided
                    sent_message = await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=message_text)
                    new_message_ids = [sent_message.message_id]

                # Update the database with the new message_ids and photos
                await db.execute('''
                    UPDATE announcements
                    SET description = ?, price = ?, message_ids = ?, photo_file_ids = ?
                    WHERE id = ?
                ''', (
                    description, price, json.dumps(new_message_ids), json.dumps(photos), ann_id
                ))
                await db.commit()

                # Confirmation to the user
                await query.message.reply_text('Ваше объявление было успешно обновлено!', reply_markup=markup)
async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'preview_edit':
        await query.message.reply_text('Что вы хотите изменить?', reply_markup=edit_markup_with_cancel)
        return EDIT_CHOICE
    elif data == 'post':
        # Проверка на наличие обязательных полей
        if not context.user_data.get('description') or not context.user_data.get('price'):
            await query.message.reply_text('Описание и цена обязательны для создания объявления.')
            return DESCRIPTION

        # Отправляем объявление и получаем ссылку
        post_link = await send_announcement(context, update)

        if post_link:
            await query.message.reply_text(f'Ваше объявление размещено!\nСсылка: {post_link}', reply_markup=markup)
        else:
            await query.message.reply_text('Произошла ошибка при размещении объявления.', reply_markup=markup)
        return CHOOSING
    elif data == 'confirm_edit':
        if 'edit_ann_id' in context.user_data:
            # Обработка редактирования существующего объявления
            ann_id = context.user_data['edit_ann_id']
            post_link = await edit_announcement(ann_id, context)

            if post_link:
                await query.message.reply_text(f'Ваше объявление было обновлено!\nСсылка: {post_link}', reply_markup=markup)
            else:
                await query.message.reply_text('Не удалось обновить объявление.', reply_markup=markup)
            return CHOOSING
        else:
            # Создание нового объявления и подтверждение редактирования
            post_link = await send_announcement(context, update)

            if post_link:
                await query.message.reply_text(f'Ваше объявление размещено!\nСсылка: {post_link}', reply_markup=markup)
            else:
                await query.message.reply_text('Произошла ошибка при размещении объявления.', reply_markup=markup)
            return CHOOSING

async def edit_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'edit_description':
        context.user_data.pop('new_description', None)
        await query.message.reply_text('Пожалуйста, отправьте новое описание.', reply_markup=cancel_markup)
        return EDIT_DESCRIPTION
    elif data == 'edit_price':
        context.user_data.pop('new_price', None)
        await query.message.reply_text('Пожалуйста, укажите новую цену.', reply_markup=cancel_markup)
        return EDIT_PRICE
    elif data == 'edit_photos':
        # Ensure `edit_ann_id` is set if editing an existing announcement
        if 'edit_ann_id' not in context.user_data:
            context.user_data['edit_ann_id'] = context.user_data.get('current_ann_id')
        context.user_data['edit_photos'] = True
        context.user_data['photos'] = []  # Reset photo list for new upload
        await query.message.reply_text(
            'Пожалуйста, отправьте новые фотографии вашего объявления. Вы можете отправить несколько фотографий по очереди.\n'
            'Когда закончите, нажмите кнопку "Закончить загрузку фото" или отправьте команду /done.',
            reply_markup=finish_photo_markup_with_cancel
        )
        return ADDING_PHOTOS
    elif data == 'cancel_edit':
        is_editing = 'edit_ann_id' in context.user_data
        await send_preview(update, context, editing=is_editing)
        return CONFIRMATION

async def edit_description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'Вернуться в меню':
        await show_menu(update, context)
        return CHOOSING

    new_description = update.message.text.strip()
    if not new_description:
        await update.message.reply_text('Описание не может быть пустым. Пожалуйста, введите описание.')
        return EDIT_DESCRIPTION

    context.user_data['new_description'] = new_description

    if 'edit_ann_id' in context.user_data:
        # Редактирование существующего объявления
        ann_id = context.user_data['edit_ann_id']

        # Получаем текущие данные объявления из базы данных
        async with aiosqlite.connect('announcements.db') as db:
            cursor = await db.execute('SELECT price, photo_file_ids FROM announcements WHERE id = ?', (ann_id,))
            row = await cursor.fetchone()
            if row:
                current_price, photo_file_ids = row
                photos = json.loads(photo_file_ids) if photo_file_ids else []
                context.user_data['photos'] = photos
                context.user_data['price'] = current_price

                # Сохраняем изменения в базу данных
                await db.execute('''
                    UPDATE announcements
                    SET description = ?
                    WHERE id = ?
                ''', (new_description, ann_id))
                await db.commit()

                # Показываем предварительный просмотр
                await send_preview(update, context, editing=True)
                return CONFIRMATION
            else:
                await update.message.reply_text('Не удалось найти объявление для редактирования.')
                return CHOOSING
    else:
        # Создание нового объявления
        await send_preview(update, context)
        return CONFIRMATION

async def edit_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'Вернуться в меню':
        await show_menu(update, context)
        return CHOOSING

    new_price = update.message.text.strip()
    if not new_price:
        await update.message.reply_text('Цена не может быть пустой. Пожалуйста, введите цену.')
        return EDIT_PRICE

    context.user_data['new_price'] = new_price

    if 'edit_ann_id' in context.user_data:
        # Редактирование существующего объявления
        ann_id = context.user_data['edit_ann_id']

        # Получаем текущие данные объявления из базы данных
        async with aiosqlite.connect('announcements.db') as db:
            cursor = await db.execute('SELECT description, photo_file_ids FROM announcements WHERE id = ?', (ann_id,))
            row = await cursor.fetchone()
            if row:
                current_description, photo_file_ids = row
                photos = json.loads(photo_file_ids) if photo_file_ids else []
                context.user_data['photos'] = photos
                context.user_data['description'] = current_description

                # Сохраняем изменения в базу данных
                await db.execute('''
                    UPDATE announcements
                    SET price = ?
                    WHERE id = ?
                ''', (new_price, ann_id))
                await db.commit()

                # Показываем предварительный просмотр
                await send_preview(update, context, editing=True)
                return CONFIRMATION
            else:
                await update.message.reply_text('Не удалось найти объявление для редактирования.')
                return CHOOSING
    else:
        # Создание нового объявления
        await send_preview(update, context)
        return CONFIRMATION

async def check_relevance(context: ContextTypes.DEFAULT_TYPE):
    user_data = context.job.data
    user_id = user_data['user_id']
    message_id = user_data['message_id']

    # Отправляем пользователю сообщение с вопросом о продлении или удалении объявления
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton('Продлить', callback_data=f'extend_{message_id}'),
            InlineKeyboardButton('Удалить', callback_data=f'remove_{message_id}')
        ]
    ])
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text='Ваше объявление скоро устареет. Хотите продлить или удалить его?',
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю: {e}")


async def delete_announcement_by_message_id(message_id, context: ContextTypes.DEFAULT_TYPE):
    # Удаляем сообщение из канала
    try:
        await context.bot.delete_message(chat_id=CHANNEL_USERNAME, message_id=message_id)
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения из канала: {e}")

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
        # Обновляем таймер на 2 недели
        context.job_queue.run_once(
            check_relevance,
            when=timedelta(weeks=2),
            data={'user_id': query.from_user.id, 'message_id': message_id}
        )
        await query.message.reply_text('Ваше объявление было продлено на 2 недели.')
    elif data.startswith('remove_'):
        message_id = int(data.split('_')[1])
        # Удаляем объявление из канала и базы данных
        await delete_announcement_by_message_id(message_id, context)
        await query.message.reply_text('Ваше объявление было удалено.')


async def send_announcement(context: ContextTypes.DEFAULT_TYPE, update: Update):
    channel_id = CHANNEL_USERNAME  # Например, '@my_channel'
    photos = context.user_data.get('photos', [])
    description = context.user_data['description']
    price = context.user_data['price']
    user = update.callback_query.from_user if update.callback_query else update.message.from_user
    username = user.username if user.username else user.first_name
    message = f"Автор: @{username}\nОписание: {description}\nЦена: {price}"

    if photos:
        media = []
        for idx, photo_id in enumerate(photos):
            if idx == 0:
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
    channel_username = CHANNEL_USERNAME.replace('@', '')
    post_link = f"https://t.me/{channel_username}/{message_ids[0]}"

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
        await query.message.reply_text('Что вы хотите изменить?', reply_markup=edit_markup_with_cancel)
        return EDIT_CHOICE
    elif data.startswith('delete_'):
        ann_id = int(data.split('_')[1])
        await delete_announcement_by_id(ann_id, context)
        await query.message.reply_text('Ваше объявление было удалено.')
        # Обновляем список объявлений
        await show_user_announcements(update, context)
        return CHOOSING
    else:
        # Обработка других callback данных, если необходимо
        pass

    return CHOOSING  # Убедимся, что бот остается в состоянии выбора действия

async def delete_announcement_by_id(ann_id, context):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if row:
            message_ids = json.loads(row[0])  # Получаем все message_id
            for message_id in message_ids:
                try:
                    await context.bot.delete_message(chat_id=CHANNEL_USERNAME, message_id=message_id)
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")

            # Удаляем запись об объявлении из базы данных
            await db.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
            await db.commit()

async def show_user_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = await get_user_announcements(user_id)

    reply_message = update.effective_message

    if not rows:
        await reply_message.reply_text('У вас пока нет объявлений.', reply_markup=markup)
        return CHOOSING  # Бот остается в состоянии выбора действия

    for row in rows:
        ann_id, message_ids_json, description, price, photo_file_ids_json = row
        message_ids = json.loads(message_ids_json)
        photos = json.loads(photo_file_ids_json) if photo_file_ids_json else []
        message = f"Описание: {description}\nЦена: {price}"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton('Редактировать', callback_data=f'edit_{ann_id}'),
                InlineKeyboardButton('Удалить', callback_data=f'delete_{ann_id}')
            ]
        ])

        if photos:
            media = []
            for idx, photo_id in enumerate(photos):
                if idx == 0:
                    media.append(InputMediaPhoto(media=photo_id, caption=message))
                else:
                    media.append(InputMediaPhoto(media=photo_id))
            await reply_message.reply_media_group(media=media)
            await reply_message.reply_text('Ваше объявление:', reply_markup=keyboard)
        else:
            await reply_message.reply_text(message, reply_markup=keyboard)

    return CHOOSING  # Бот остается в состоянии выбора действия

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем все данные пользователя
    context.user_data.clear()
    await update.message.reply_text(
        'Действие отменено.',
        reply_markup=add_advertisement_keyboard
    )
    return CHOOSING

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

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

    # Проверяем, подписан ли пользователь
    is_user_subscribed = await is_subscribed(user_id, context)

    if is_user_subscribed:
        # Вызываем функцию show_menu для отображения соответствующего меню
        await show_menu(update, context)
        return CHOOSING
    else:
        # Пользователь не подписан: уведомляем об этом
        await query.message.reply_text(
            'Вы еще не подписались на канал. Пожалуйста, подпишитесь, чтобы продолжить.',
            reply_markup=check_subscription_message()[1]  # Повторно показываем кнопки
        )
        return CHECK_SUBSCRIPTION