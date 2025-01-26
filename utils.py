import aiosqlite
from telegram.ext import ContextTypes
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from config import PRIVATE_CHANNEL_ID, INVITE_LINK

from logger import logger
from datetime import datetime
import pytz

from database import has_user_ads
from keyboards import markup, add_advertisement_keyboard
from texts import CHOOSE_ACTION_NEW


async def is_subscribed(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(chat_id=PRIVATE_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        return False


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    has_ads = await has_user_ads(user_id)

    if update.message:
        # Responding to a regular message
        if has_ads:
            await update.message.reply_text(
                CHOOSE_ACTION_NEW,
                reply_markup=markup  # Two buttons
            )
        else:
            await update.message.reply_text(
                CHOOSE_ACTION_NEW,
                reply_markup=add_advertisement_keyboard  # Single button
            )
    elif update.callback_query:
        # Responding to a callback query
        if has_ads:
            await update.callback_query.message.reply_text(
                CHOOSE_ACTION_NEW,
                reply_markup=markup  # Two buttons
            )
        else:
            await update.callback_query.message.reply_text(
                CHOOSE_ACTION_NEW,
                reply_markup=add_advertisement_keyboard  # Single button
            )

async def check_subscription_message():
    text = 'Пожалуйста, подпишитесь на наш канал, чтобы продолжить.'
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('Подписаться на канал', url=INVITE_LINK)],
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

def get_private_channel_post_link(channel_id, message_id):
    channel_id_str = str(channel_id)
    if channel_id_str.startswith('-100'):
        channel_id_str = channel_id_str[4:]
    return f"https://t.me/c/{channel_id_str}/{message_id}"

async def notify_owner_about_comment(context, message_id, user_id, text):
    """Отправляет уведомление владельцу объявления, если комментарий оставил не он сам."""
    try:
        async with aiosqlite.connect('announcements.db') as db:
            cursor = await db.execute("SELECT id, user_id, message_ids FROM announcements")
            rows = await cursor.fetchall()

        # 🔍 Ищем объявление, содержащее данный message_id
        announcement = None
        for row in rows:
            ann_id, owner_id, message_ids = row
            message_ids_list = eval(message_ids) if isinstance(message_ids, str) else message_ids
            if message_id in message_ids_list:
                announcement = (ann_id, owner_id)
                break

        if not announcement:
            logger.error(f"❌ [notify_owner_about_comment] Объявление с message_id={message_id} не найдено.")
            return

        ann_id, owner_id = announcement

        # 🔍 Проверяем, что комментарий оставил НЕ владелец объявления
        if owner_id == user_id:
            logger.info(f"🔕 [notify_owner_about_comment] Владелец {owner_id} сам оставил комментарий. Уведомление не требуется.")
            return

        # 🔗 Создаём ссылку на объявление
        announcement_link = get_private_channel_post_link(PRIVATE_CHANNEL_ID, message_id)

        # 📩 Формируем сообщение
        message_text = f"💬 Новый комментарий к вашему объявлению #{ann_id}:\n\n_{text}_\n\n🔗 [Посмотреть объявление]({announcement_link})"

        # ✉️ Отправляем уведомление владельцу
        await context.bot.send_message(
            chat_id=owner_id,
            text=message_text,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        logger.info(f"📨 [notify_owner_about_comment] Уведомление отправлено владельцу {owner_id}.")

    except Exception as e:
        logger.error(f"❌ [notify_owner_about_comment] Ошибка: {e}")
