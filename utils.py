from telegram.ext import ContextTypes
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from config import CHANNEL_USERNAME
import logging

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
    user_id = update.effective_user.id
    if await has_user_ads(user_id):
        # Существующий пользователь: показываем меню с двумя кнопками
        await update.message.reply_text(
            'Выберите действие:',
            reply_markup=markup  # Клавиатура с двумя кнопками: «Добавить объявление» и «Мои объявления»
        )
    else:
        # Новый пользователь: показываем только кнопку «Добавить объявление»
        await update.message.reply_text(
            'Вы можете добавить свое первое объявление.',
            reply_markup=add_advertisement_keyboard  # Клавиатура с одной кнопкой: «Добавить объявление»
        )

async def check_subscription_message():
    text = 'Пожалуйста, подпишитесь на наш канал, чтобы продолжить.'
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('Подписаться на канал', url=f'https://t.me/{CHANNEL_USERNAME.replace("@", "")}')],
        [InlineKeyboardButton('Я подписался', callback_data='check_subscription')]
    ])
    return text, keyboard
