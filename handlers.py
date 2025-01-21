import telegram
from telegram import Update, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from datetime import datetime
from config import *
from keyboards import *
from utils import is_subscribed, show_menu, check_subscription_message, get_serbia_time
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
        return DESCRIPTION
    elif choice == MY_ADS_CHOICE:
        await show_user_announcements(update, context)
        return CHOOSING
    else:
        await update.message.reply_text(CHOOSE_ACTION, reply_markup=markup)
        return CHOOSING

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

        # Получаем ID объявления
        ann_id = context.user_data.get('ann_id')

        if not ann_id:
            await query.message.reply_text("Ошибка: ID объявления не найден.", reply_markup=markup)
            return CHOOSING

        # Отправляем объявление в канал и получаем ссылку на пост
        post_link = await publish_announcement(update, context, ann_id)

        if post_link:
            await query.message.reply_text(POST_SUCCESS_MESSAGE.format(post_link), reply_markup=markup, parse_mode='Markdown')
        else:
            await query.message.reply_text(POST_FAILURE_MESSAGE, reply_markup=markup)

        return CHOOSING

async def edit_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    try:
        await query.message.delete()
    except telegram.error.BadRequest:
        pass

    if data == 'edit_description':
        context.user_data['is_editing'] = True
        await query.message.reply_text(EDIT_DESCRIPTION_PROMPT, reply_markup=ReplyKeyboardRemove())
        return EDIT_DESCRIPTION

    elif data == 'edit_price':
        context.user_data['is_editing'] = True
        await query.message.reply_text(EDIT_PRICE_PROMPT, reply_markup=ReplyKeyboardRemove())
        return EDIT_PRICE

    elif data == 'edit_photos':
        context.user_data['is_editing'] = True
        context.user_data['photos'] = []
        await query.message.reply_text(EDIT_PHOTOS_PROMPT, reply_markup=finish_photo_markup_with_cancel)
        return ADDING_PHOTOS

    elif data == 'cancel_edit':
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
