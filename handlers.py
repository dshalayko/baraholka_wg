from telegram import Update, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from datetime import datetime
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

    # Проверяем подписку
    if not await is_subscribed(user_id, context):
        text, keyboard = await check_subscription_message()
        await update.message.reply_text(text, reply_markup=keyboard)
        return CHECK_SUBSCRIPTION
    else:
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [InlineKeyboardButton("Добавить обьявление", callback_data='add_advertisement')],
            [InlineKeyboardButton("Мои обьявления", callback_data='my_advertisements')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Проверяем, есть ли у пользователя объявления
        if await has_user_ads(user_id):
            # Существующий пользователь: показываем меню с двумя кнопками
            await update.message.reply_text('Выберите действие:⤵️', reply_markup=reply_markup)
        else:
            # Новый пользователь: показываем только кнопку «Добавить объявление»
            await update.message.reply_text(
                '💥Вы можете добавить свое первое объявление.',
                reply_markup=reply_markup
            )
        return CHOOSING

async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Обработка кнопки "Добавить обьявление"
    if query.data == 'add_advertisement':
        await handle_choice(update, context)

    # Обработка кнопки "Мои обьявления"
    elif query.data == 'my_advertisements':
        await show_user_announcements(update, context)

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if await is_subscribed(user_id, context):
        await query.message.reply_text(
            'Спасибо за подписку! 💃🏻',
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

        # Убираем клавиатуру с кнопкой "Вернуться в меню"
        await update.message.reply_text('Пожалуйста, отправьте описание вашего объявления.', reply_markup=ReplyKeyboardRemove())
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


# Добавляем новую функцию для опубликованных объявлений
async def adding_photos_published(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Начало функции добавления фотографий для опубликованного объявления. User ID: {update.effective_user.id}")

    # Обрабатываем нажатие кнопки "Вернуться в меню"
    if update.message.text == 'Вернуться в меню':
        await show_menu(update, context)
        return CHOOSING

    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        # Проверка на количество фотографий
        if len(context.user_data['photos']) < 10:
            photo = update.message.photo[-1]
            context.user_data['photos'].append(photo.file_id)
            logger.info(f"Добавлено фото: {photo.file_id}")

            # Отправляем сообщение один раз после загрузки первого фото
            if len(context.user_data['photos']) == 1:
                await update.message.reply_text(
                    'Фото добавлено. Вы можете отправить еще одно или нажать "Закончить загрузку фото".',
                    reply_markup=finish_photo_markup_with_cancel
                )
        elif 'limit_reached' not in context.user_data:
            # Предупреждаем о лимите и сохраняем флаг, чтобы не отправлять это сообщение повторно
            await update.message.reply_text('Вы можете загрузить не более 10 фотографий. Лишние фото не будут сохранены.')
            context.user_data['limit_reached'] = True

    elif update.message.text == 'Закончить загрузку фото':
        logger.info("Пользователь завершил загрузку фото для опубликованного объявления.")

        # Скрываем клавиатуру
        await update.message.reply_text(
            "Обработка фотографий...",
            reply_markup=ReplyKeyboardRemove()  # Убираем клавиатуру
        )

        # Проверяем, есть ли описание и цена в контексте
        if not context.user_data.get('description') or not context.user_data.get('price'):
            ann_id = context.user_data.get('edit_ann_id')
            logger.info(f"Редактирование опубликованного объявления с ID: {ann_id}")

            async with aiosqlite.connect('announcements.db') as db:
                cursor = await db.execute('SELECT description, price FROM announcements WHERE id = ?', (ann_id,))
                row = await cursor.fetchone()
                if row:
                    context.user_data['description'], context.user_data['price'] = row
                    logger.info(f"Загруженные описание и цена из базы: {context.user_data['description']}, {context.user_data['price']}")
                else:
                    await update.message.reply_text('Не удалось найти объявление для редактирования.')
                    return CHOOSING

        await send_preview(update, context, editing=True)
        return CONFIRMATION

    else:
        await update.message.reply_text('Пожалуйста, отправьте фотографию или нажмите "Закончить загрузку фото".')
    return ADDING_PHOTOS

# Добавляем новую функцию для неопубликованных объявлений
async def adding_photos_unpublished(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Начало функции добавления фотографий для неопубликованного объявления. User ID: {update.effective_user.id}")

    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        # Проверка на количество фотографий
        if len(context.user_data['photos']) < 10:
            photo = update.message.photo[-1]
            context.user_data['photos'].append(photo.file_id)
            logger.info(f"Добавлено фото: {photo.file_id}")

            # Отправляем сообщение один раз после загрузки первого фото
            if len(context.user_data['photos']) == 1:
                await update.message.reply_text(
                    'Фото добавлено. Вы можете отправить еще одно или нажать "Закончить загрузку фото".',
                    reply_markup=finish_photo_markup_with_cancel
                )
        elif 'limit_reached' not in context.user_data:
            # Предупреждаем о лимите и сохраняем флаг, чтобы не отправлять это сообщение повторно
            await update.message.reply_text('Вы можете загрузить не более 10 фотографий. Лишние фото не будут сохранены.')
            context.user_data['limit_reached'] = True

    elif update.message.text == 'Объявление без фото':
        logger.info("Пользователь выбрал создание объявления без фото.")

        # Скрываем клавиатуру
        await update.message.reply_text(
            "Обработка объявления без фото...",
            reply_markup=ReplyKeyboardRemove()  # Убираем клавиатуру
        )

        if not context.user_data.get('description') or not context.user_data.get('price'):
            await update.message.reply_text('❗Описание и цена обязательны для создания объявления.')
            return ADDING_PHOTOS

        await send_preview(update, context, editing=False)
        return CONFIRMATION

    elif update.message.text == 'Закончить загрузку фото':
        logger.info("Пользователь завершил загрузку фото для неопубликованного объявления.")

        # Скрываем клавиатуру
        await update.message.reply_text(
            "Обработка фотографий...",
            reply_markup=ReplyKeyboardRemove()  # Убираем клавиатуру
        )

        if not context.user_data.get('description') or not context.user_data.get('price'):
            await update.message.reply_text('❗Описание и цена обязательны для создания объявления.')
            return ADDING_PHOTOS

        await send_preview(update, context, editing=False)
        return CONFIRMATION

    else:
        await update.message.reply_text(
            'Пожалуйста, отправьте фотографию или нажмите "Закончить загрузку фото" либо "Объявление без фото".'
        )
    return ADDING_PHOTOS

# Вносим изменения в основной обработчик
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
    await update.message.reply_text('Теперь укажите цену.')  # Убираем кнопку "Вернуться в меню"
    return PRICE

async def price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = update.message.text.strip()

    # Установим ограничение на 255 символов для цены (можно менять по необходимости)
    if len(price) > 255:
        await update.message.reply_text(f'❗Цена слишком длинная. Максимум 255 символов. Сейчас: {len(price)} символов.')
        return PRICE

    if not price:
        await update.message.reply_text('❗Цена не может быть пустой. Пожалуйста, введите цену.')
        return PRICE

    context.user_data['price'] = price
    await update.message.reply_text(
        'Теперь отправьте фото вашего объявления.\n'
        'Когда закончите, нажмите кнопку "Закончить загрузку фото"\n'
        'Если хотите создать объявление без фото, нажмите кнопку ниже.',
        reply_markup=photo_markup_with_cancel  # Оставляем кнопки для фото
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

    # Убираем текущую клавиатуру (если она активна)
    if update.message and update.message.reply_markup:
        await update.message.reply_text(
            "Ожидайте предварительный просмотр...",
            reply_markup=ReplyKeyboardRemove()  # Убираем текущую клавиатуру
        )

    # Проверяем, является ли это редактированием опубликованного объявления
    if editing and 'edit_ann_id' in context.user_data:
        ann_id = context.user_data.get('edit_ann_id')

        # Проверяем, опубликовано ли объявление (по наличию ann_id)
        async with aiosqlite.connect('announcements.db') as db:
            cursor = await db.execute('SELECT * FROM announcements WHERE id = ?', (ann_id,))
            row = await cursor.fetchone()
            if row:
                current_time = datetime.now().strftime('%d %B %Y')
                message += f"\n\n🆙 {current_time}"

    # Обрезаем сообщение до 1024 символов
    if len(message) > 1024:
        message = message[:1024]

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

async def confirm_edit_unpublished(context):
    logger.info("Начало функции confirm_edit_unpublished")

    # Используем новые значения описания и цены, если они были предоставлены
    description = context.user_data.get('new_description', context.user_data.get('description'))
    price = context.user_data.get('new_price', context.user_data.get('price'))
    photos = context.user_data.get('photos', [])

    # Получаем username или first_name для автора объявления
    username = context.user_data['username']

    logger.info(f"Описание: {description}, Цена: {price}, Фото: {photos}, Автор: {username}")

    # Формируем сообщение с указанием автора
    message_text = f"Автор: @{username}\nОписание: {description}\nЦена: {price}"

    # Отправляем фото или текст, если фото нет
    if photos:
        media = []
        for idx, photo_id in enumerate(photos):
            if idx == 0:
                media.append(InputMediaPhoto(media=photo_id, caption=message_text))
            else:
                media.append(InputMediaPhoto(media=photo_id))

        sent_messages = await context.bot.send_media_group(chat_id=CHANNEL_USERNAME, media=media)
        message_ids = [msg.message_id for msg in sent_messages]
        logger.info(f"Фотографии отправлены, новые message_ids: {message_ids}")
    else:
        sent_message = await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=message_text)
        message_ids = [sent_message.message_id]
        logger.info(f"Отправлено текстовое сообщение, message_id: {message_ids[0]}")

    # Сохраняем объявление в базе данных и получаем его ID
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('''
            INSERT INTO announcements (user_id, username, message_ids, description, price, photo_file_ids)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            context.user_data['user_id'],  # ID пользователя
            context.user_data['username'],  # Имя пользователя
            json.dumps(message_ids),  # ID сообщений
            description,
            price,
            json.dumps(photos)
        ))
        ann_id = cursor.lastrowid  # Получаем ID нового объявления
        await db.commit()

    # Сохраняем ID объявления в context.user_data
    context.user_data['edit_ann_id'] = ann_id  # Эта строка важна

    logger.info(f"Объявление успешно сохранено в базе данных с ID: {ann_id}")

    # Формируем ссылку на объявление
    channel_username = CHANNEL_USERNAME.replace('@', '')
    post_link = f"https://t.me/{channel_username}/{message_ids[0]}"
    logger.info(f"Ссылка на новое объявление: {post_link}")

    return post_link

async def confirm_edit_published(context, update, ann_id):
    logger.info(f"Начало функции confirm_edit_published для объявления ID: {ann_id}")

    # Проверим, что данные в контексте корректны
    description = context.user_data.get('new_description', context.user_data.get('description'))
    price = context.user_data.get('new_price', context.user_data.get('price'))
    photos = context.user_data.get('photos', [])

    # Получаем username или first_name для автора объявления
    username = context.user_data['username']

    logger.info(f"Описание: {description}, Цена: {price}, Фотографии: {photos}, Автор: {username}")

    # Формируем текст с "Обновлено" для опубликованного объявления
    current_time = datetime.now().strftime('%d %B %Y')
    message_text = f"Автор: @{username}\nОписание: {description}\nЦена: {price}\n\nОбновлено {current_time}"

    # Получаем старые message_ids для удаления
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()

        if row:
            old_message_ids = json.loads(row[0])
            logger.info(f"Старые message_ids для удаления: {old_message_ids}")

            # Удаляем старые сообщения
            await remove_old_photos(old_message_ids, context)

            # Формируем текст с "Обновлено" для опубликованного объявления
            current_time = datetime.now().strftime('%d %B %Y')
            message_text = f"Описание: {description}\nЦена: {price}\n\n🆙 {current_time}"

            # Отправляем новые фото и текст
            if photos:
                media = []
                for idx, photo_id in enumerate(photos):
                    if idx == 0:
                        media.append(InputMediaPhoto(media=photo_id, caption=message_text))
                    else:
                        media.append(InputMediaPhoto(media=photo_id))

                sent_messages = await context.bot.send_media_group(chat_id=CHANNEL_USERNAME, media=media)
                new_message_ids = [msg.message_id for msg in sent_messages]
                logger.info(f"Новые фотографии отправлены, новые message_ids: {new_message_ids}")
            else:
                sent_message = await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=message_text)
                new_message_ids = [sent_message.message_id]
                logger.info(f"Отправлено текстовое сообщение, message_id: {new_message_ids[0]}")

            # Обновляем данные в базе данных
            await db.execute('''
                UPDATE announcements
                SET description = ?, price = ?, message_ids = ?, photo_file_ids = ?
                WHERE id = ?
            ''', (
                description, price, json.dumps(new_message_ids), json.dumps(photos), ann_id
            ))
            await db.commit()

            logger.info("Объявление успешно обновлено в базе данных.")

            # Корректируем формирование ссылки
            channel_username = CHANNEL_USERNAME.replace('@', '')  # Убираем @ из названия канала
            post_link = f"https://t.me/{channel_username}/{new_message_ids[0]}"
            logger.info(f"Ссылка на обновленное объявление: {post_link}")

            return post_link
        else:
            logger.error(f"Не удалось найти объявление с ID {ann_id}.")
            return None


async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    logger.info(f"Начало функции confirmation_handler с данными: {data}")

    if data == 'preview_edit':
        await query.message.reply_text('Что вы хотите изменить?', reply_markup=edit_markup_with_cancel)
        return EDIT_CHOICE

    elif data == 'post':
        logger.info("Пользователь выбрал размещение объявления.")

        # Если нет user_id в контексте, устанавливаем его
        if 'user_id' not in context.user_data:
            context.user_data['user_id'] = query.from_user.id  # Получаем ID пользователя из callback запроса

        # Проверим, опубликованное ли это объявление или нет
        ann_id = context.user_data.get('edit_ann_id')

        if ann_id:
            logger.info(f"Редактируемое объявление ID: {ann_id}")
            post_link = await confirm_edit_published(context, update, ann_id)
        else:
            logger.info(f"Новое объявление, создание с нуля.")
            post_link = await confirm_edit_unpublished(context)

        if post_link:
            await query.message.reply_text(f'💥Ваше объявление размещено!\nСсылка: {post_link}', reply_markup=markup)
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
        await update.message.reply_text('❗Описание не может быть пустым. Пожалуйста, введите описание.')
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
                await update.message.reply_text('❗Не удалось найти объявление для редактирования.')
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
        await update.message.reply_text('❗Цена не может быть пустой. Пожалуйста, введите цену.')
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
                await update.message.reply_text('❗Не удалось найти объявление для редактирования.')
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

    # Получаем username или first_name для автора объявления
    user = update.callback_query.from_user if update.callback_query else update.message.from_user
    username = user.username if user.username else user.first_name
    context.user_data['username'] = username

    # Формируем сообщение с указанием автора
    message = f"Автор: @{username}\nОписание: {description}\nЦена: {price}"

    # Обрезаем сообщение до 1024 символов
    if len(message) > 1024:
        message = message[:1024]

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
        await delete_announcement_by_id(ann_id, context, query)
        await query.message.reply_text('Ваше объявление было удалено.')
        return CHOOSING
    else:
        # Обработка других callback данных, если необходимо
        pass

    return CHOOSING  # Убедимся, что бот остается в состоянии выбора действия

async def delete_announcement_by_id(ann_id, context, query):
    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids, photo_file_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if row:
            message_ids = json.loads(row[0])  # Получаем все message_id из канала
            photos = json.loads(row[1]) if row[1] else []

            # Удаляем сообщения в канале
            for message_id in message_ids:
                try:
                    await context.bot.delete_message(chat_id=CHANNEL_USERNAME, message_id=message_id)
                    logger.info(f"Сообщение с ID {message_id} удалено из канала.")
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")

            # Удаляем запись об объявлении из базы данных
            await db.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
            await db.commit()

            # Удаляем сообщение с объявлениями у пользователя без отправки нового
            try:
                await query.message.delete()
                logger.info("Сообщение с объявлением у пользователя удалено.")
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения у пользователя: {e}")


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

        # Формируем сообщение с ограничением по длине
        message = f"Описание: {description}\nЦена: {price}"
        if len(message) > 1024:
            message = message[:1024]

        # Добавляем ссылку на полную версию объявления, если больше одной фотографии
        if len(photos) > 1:
            channel_username = CHANNEL_USERNAME.replace('@', '')  # Убираем @ из названия канала
            post_link = f"https://t.me/{channel_username}/{message_ids[0]}"
            message += f"\n\n[Смотреть полную версию с фотографиями]({post_link})"

        # Формируем клавиатуру с кнопками "Редактировать" и "Удалить"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton('Редактировать', callback_data=f'edit_{ann_id}'),
                InlineKeyboardButton('Удалить', callback_data=f'delete_{ann_id}')
            ]
        ])

        # Если есть фотографии, отправляем только первую с кнопками и ссылкой на полную версию
        if photos:
            await reply_message.reply_photo(photo=photos[0], caption=message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            # Если нет фотографий, отправляем просто текст объявления с кнопками
            await reply_message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

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
        # Получаем сообщение и клавиатуру для проверки подписки
        text, keyboard = await check_subscription_message()

        # Пользователь не подписан: уведомляем об этом
        await query.message.reply_text(
            text,  # Сообщение о необходимости подписки
            reply_markup=keyboard  # Повторно показываем кнопки
        )
        return CHECK_SUBSCRIPTION