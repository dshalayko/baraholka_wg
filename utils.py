from telegram.ext import ContextTypes
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from config import CHANNEL_USERNAME
import logging
from datetime import datetime
import pytz

from database import has_user_ads
from keyboards import markup, add_advertisement_keyboard

logger = logging.getLogger(__name__)

async def is_subscribed(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status != 'left'
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        return False

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show the menu with options based on whether the user has ads or not.
    :param update: The update object containing message or callback query.
    :param context: The bot context for this interaction.
    """
    user_id = update.effective_user.id

    # Check if the user has ads
    has_ads = await has_user_ads(user_id)

    # Check if it's a message or a callback query
    if update.message:
        # Responding to a regular message
        if has_ads:
            await update.message.reply_text(
                'Выберите действие:',
                reply_markup=markup  # Two buttons
            )
        else:
            await update.message.reply_text(
                'Вы можете добавить свое первое объявление.',
                reply_markup=add_advertisement_keyboard  # Single button
            )
    elif update.callback_query:
        # Responding to a callback query
        if has_ads:
            await update.callback_query.message.reply_text(
                'Выберите действие:',
                reply_markup=markup  # Two buttons
            )
        else:
            await update.callback_query.message.reply_text(
                'Вы можете добавить свое первое объявление.',
                reply_markup=add_advertisement_keyboard  # Single button
            )

async def check_subscription_message():
    text = 'Пожалуйста, подпишитесь на наш канал, чтобы продолжить.'
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('Подписаться на канал', url=f'https://t.me/{CHANNEL_USERNAME.replace("@", "")}')],
        [InlineKeyboardButton('Я подписался', callback_data='check_subscription')]
    ])
    return text, keyboard


def get_serbia_time():
    # Определяем временную зону для Сербии (Europe/Belgrade)
    serbia_tz = pytz.timezone('Europe/Belgrade')

    # Получаем текущее время в UTC и переводим в часовую зону Сербии
    serbia_time = datetime.now(pytz.utc).astimezone(serbia_tz)

    # Форматируем время в нужный формат
    formatted_time = serbia_time.strftime('%d.%m.%Y в %H:%M')

    return formatted_time