import aiosqlite
from telegram.ext import ContextTypes
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.helpers import escape_markdown
from telegram.constants import ParseMode
from config import PRIVATE_CHANNEL_ID, INVITE_LINK, DB_PATH

from logger import logger
from datetime import datetime
import pytz

from database import has_user_ads
from keyboards import (
    get_markup,
    get_add_advertisement_keyboard,
)
from texts import (
    t,
    get_lang,
    SUBSCRIPTION_PROMPT,
    I_SUBSCRIBED_BUTTON,
    COMMENT_NOTIFICATION,
)


async def is_subscribed(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(chat_id=PRIVATE_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        return False

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(update)

    has_ads = await has_user_ads(user_id)

    if update.message:
        # Responding to a regular message
        if has_ads:
            await update.message.reply_text(
                t("CHOOSE_ACTION_NEW", lang),
                reply_markup=get_markup(lang)  # Two buttons
            )
        else:
            await update.message.reply_text(
                t("CHOOSE_ACTION_NEW", lang),
                reply_markup=get_add_advertisement_keyboard(lang)  # Single button
            )
    elif update.callback_query:
        # Responding to a callback query
        if has_ads:
            await update.callback_query.message.reply_text(
                t("CHOOSE_ACTION_NEW", lang),
                reply_markup=get_markup(lang)  # Two buttons
            )
        else:
            await update.callback_query.message.reply_text(
                t("CHOOSE_ACTION_NEW", lang),
                reply_markup=get_add_advertisement_keyboard(lang)  # Single button
            )

async def check_subscription_message(update: Update):
    lang = get_lang(update)
    text = t("SUBSCRIPTION_PROMPT", lang)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("I_SUBSCRIBED_BUTTON", lang), callback_data='check_subscription')]
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
        logger.info(f"🚀 [notify_owner_about_comment] Запуск с message_id={message_id}, user_id={user_id}")

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT id, user_id, message_ids FROM announcements")
            rows = await cursor.fetchall()

        logger.info(f"🔍 [notify_owner_about_comment] Найдено {len(rows)} объявлений в базе, ищем соответствие message_id...")

        announcement = None
        for row in rows:
            ann_id, owner_id, message_ids = row
            logger.info(f"📌 [notify_owner_about_comment] Проверяем объявление {ann_id} (владелец {owner_id})")

            if not message_ids:
                logger.warning(f"⚠️ [notify_owner_about_comment] У объявления {ann_id} отсутствуют message_ids, пропускаем.")
                continue

            message_ids_list = eval(message_ids) if isinstance(message_ids, str) else message_ids
            if message_id in message_ids_list:
                announcement = (ann_id, owner_id)
                logger.info(f"✅ [notify_owner_about_comment] Найдено соответствующее объявление: ID {ann_id}, владелец {owner_id}")
                break

        if not announcement:
            logger.error(f"❌ [notify_owner_about_comment] Объявление с message_id={message_id} не найдено.")
            return

        ann_id, owner_id = announcement

        if owner_id == user_id:
            logger.info(f"🔕 [notify_owner_about_comment] Владелец {owner_id} сам оставил комментарий. Уведомление не требуется.")
            return

        announcement_link = get_private_channel_post_link(PRIVATE_CHANNEL_ID, message_id)

        escaped_text = escape_markdown(text, version=2)

        lang = 'en'
        try:
            user = await context.bot.get_chat(owner_id)
            lang = get_lang(user)
        except Exception:
            pass

        # 📩 Формируем сообщение
        message_text = t("COMMENT_NOTIFICATION", lang).format(
            text=escaped_text,
            link=announcement_link,
        )

        # ✉️ Отправляем уведомление владельцу
        logger.info(f"📨 [notify_owner_about_comment] Отправляем уведомление владельцу {owner_id}...")
        await context.bot.send_message(
            chat_id=owner_id,
            text=message_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True
        )
        logger.info(f"✅ [notify_owner_about_comment] Уведомление успешно отправлено владельцу {owner_id}.")

    except Exception as e:
        logger.error(f"❌ [notify_owner_about_comment] Ошибка: {e}")
