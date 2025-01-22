import telegram
from utils import is_subscribed, show_menu, check_subscription_message
from texts import *  # Импортируем все тексты
from database import (
    save_announcement,
    delete_announcement_by_id as db_delete_announcement_by_id,
    has_user_ads, edit_announcement, update_announcement_description, get_announcement_for_edit,
    update_announcement_price
)

from announcements import *

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
        await create_announcement(update, context)  # Теперь создаём объявление перед вводом описания
        return EDIT_DESCRIPTION
    elif choice == MY_ADS_CHOICE:
        await show_user_announcements(update, context)
        return CHOOSING
    else:
        await update.message.reply_text(CHOOSE_ACTION, reply_markup=markup)
        return CHOOSING

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


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split('_')
    action = parts[0]
    ann_id = int(parts[1]) if len(parts) > 1 else None

    logger.info(f"📌 [button_handler] Нажата кнопка: {data}, действие: {action}, ID объявления: {ann_id}")

    if not ann_id:
        logger.error("❌ Ошибка: не удалось определить ID объявления.")
        await query.message.reply_text("❌ Ошибка: не удалось определить ID объявления.")
        return CHOOSING

    async with aiosqlite.connect('announcements.db') as db:
        cursor = await db.execute('SELECT message_ids FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if row:
            message_ids_json = row[0]
            message_ids = json.loads(message_ids_json) if message_ids_json else None
            is_editing = bool(message_ids)  # True, если message_ids есть
        else:
            is_editing = False

    context.user_data['ann_id'] = ann_id
    context.user_data['is_editing'] = is_editing

    try:
        await query.message.delete()
    except telegram.error.BadRequest:
        pass

    if action == 'editdescription':
        logger.info(f"✏️ Вызов функции: description_received(), ID объявления: {ann_id}")
        await query.message.reply_text(EDIT_DESCRIPTION_PROMPT, reply_markup=ReplyKeyboardRemove())
        return EDIT_DESCRIPTION

    elif action == 'editprice':
        logger.info(f"💰 Вызов функции: price_received(), ID объявления: {ann_id}")
        await query.message.reply_text(EDIT_PRICE_PROMPT, reply_markup=ReplyKeyboardRemove())
        return EDIT_PRICE

    elif action == 'editphotos':
        logger.info(f"🖼️ Вызов функции: adding_photos(), ID объявления: {ann_id}")
        context.user_data['photos'] = []
        await query.message.reply_text(EDIT_PHOTOS_PROMPT, reply_markup=finish_photo_markup_with_cancel)
        return ADDING_PHOTOS

    elif action == 'delete':
        logger.info(f"❌ Вызов функции: delete_announcement_by_id(), ID объявления: {ann_id}")
        await delete_announcement_by_id(ann_id, context, query)
        return CHOOSING

    elif action == 'up':
        logger.info(f"🔼 Вызов функции: поднятие объявления, ID объявления: {ann_id}")
        await query.message.reply_text("🔼 Объявление поднято!")
        return CHOOSING

    elif action == 'post':
        logger.info(f"📢 Вызов функции: publish_announcement(), ID объявления: {ann_id}")
        post_link = await publish_announcement(update, context, ann_id)

        if post_link:
            await query.message.reply_text(POST_SUCCESS_MESSAGE.format(post_link), reply_markup=markup, parse_mode='Markdown')
        else:
            await query.message.reply_text(POST_FAILURE_MESSAGE, reply_markup=markup)

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
