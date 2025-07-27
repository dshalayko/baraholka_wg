from utils import is_subscribed, show_menu, check_subscription_message
from keyboards import get_markup, get_add_advertisement_keyboard
from database import (
    has_user_ads,
)
from announcements import *
from texts import (
    t,
    get_lang,
)
import logging
import aiosqlite
from telegram.constants import ParseMode
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.ext import ContextTypes

from logger import logger

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start, отправляет приветственное сообщение и удаляет команду пользователя."""
    user_id = update.message.from_user.id
    start_message_id = update.message.message_id

    lang = get_lang(update)

    if not await is_subscribed(user_id, context):
        text, keyboard = await check_subscription_message(update)
        await update.message.reply_text(text, reply_markup=keyboard)
        return CHECK_SUBSCRIPTION

    if await has_user_ads(user_id):
        welcome_message = await update.message.reply_text(t("WELCOME_NEW_USER", lang), reply_markup=get_markup(lang))
    else:
        welcome_message = await update.message.reply_text(t("WELCOME_NEW_USER", lang), reply_markup=get_add_advertisement_keyboard(lang))

    context.user_data["welcome_message_id"] = welcome_message.message_id
    logger.info(f"✅ [start] Сохранен message_id приветствия: {welcome_message.message_id}")

    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=start_message_id)
        logger.info(f"🗑️ [start] Удалено сообщение пользователя: /start (message_id={start_message_id})")
    except telegram.error.BadRequest:
        logger.warning(f"⚠️ [start] Не удалось удалить сообщение /start (message_id={start_message_id})")

    return CHOOSING

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    lang = get_lang(update)
    if await is_subscribed(user_id, context):
        await query.message.reply_text(t("SUBSCRIPTION_SUCCESS", lang))
        await show_menu(update, context)
        return CHOOSING
    else:
        text, keyboard = await check_subscription_message(update)
        await query.message.reply_text(t("NOT_SUBSCRIBED_YET", lang), reply_markup=keyboard)
        return

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message:
        user_message = update.message
        user_message_id = user_message.message_id
        chat_id = user_message.chat_id
        choice = user_message.text
    else:
        logger.warning("⚠️ [handle_choice] update.message отсутствует. Вероятно, вызван через callback_query.")
        return CHOOSING

    logger.info(f"📝 [handle_choice] Пользователь выбрал: {choice}")

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=user_message_id)
        logger.info(f"🗑️ [handle_choice] Удалено сообщение пользователя: {choice} (message_id={user_message_id})")
    except telegram.error.BadRequest:
        logger.warning(f"⚠️ [handle_choice] Не удалось удалить сообщение пользователя {choice} (message_id={user_message_id})")

    bot_message_id = context.user_data.pop("welcome_message_id", None)  # Удаляем сразу после использования

    if bot_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=bot_message_id)
            logger.info(f"🗑️ [handle_choice] Удалено сообщение бота: WELCOME_NEW_USER (message_id={bot_message_id})")
        except telegram.error.BadRequest:
            logger.warning(f"⚠️ [handle_choice] Не удалось удалить WELCOME_NEW_USER (message_id={bot_message_id})")

    lang = get_lang(update)

    if choice == t("NEW_AD_CHOICE", lang):
        context.user_data.clear()
        return await create_announcement(update, context)

    elif choice == t("MY_ADS_CHOICE", lang):
        return await show_user_announcements(update, context)

    else:
        await update.effective_chat.send_message(t("CHOOSE_ACTION", lang), reply_markup=get_markup(lang))
        return CHOOSING

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = get_lang(update)

    data = query.data
    logger.info(f"🔍 [button_handler] Получен callback_data: {data}")

    parts = data.split('_')
    action = parts[0]
    ann_id = int(parts[1]) if len(parts) > 1 else None

    logger.info(f"📌 [button_handler] Нажата кнопка: {data}, действие: {action}, ID объявления: {ann_id}")

    if not ann_id:
        logger.error("❌ Ошибка: не удалось определить ID объявления из callback_data.")
        await query.message.reply_text(t("ERROR_CANNOT_DETERMINE_ID", lang))
        return CHOOSING

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT id FROM announcements WHERE id = ?', (ann_id,))
        row = await cursor.fetchone()
        if not row:
            logger.error(f"❌ Ошибка: объявление {ann_id} не найдено в БД.")
            await query.message.reply_text(t("ERROR_ANNOUNCEMENT_NOT_FOUND_DB", lang))
            return CHOOSING

    context.user_data['ann_id'] = ann_id
    context.user_data['is_editing'] = True

    logger.info(f"📋 [button_handler] is_editing=True, ID объявления: {ann_id}")

    try:
        await query.message.delete()
    except telegram.error.BadRequest:
        pass

    if action == 'editdescription':
        logger.info(f"✏️ Вызов функции: description_received(), ID объявления: {ann_id}")
        await query.message.reply_text(t("EDIT_DESCRIPTION_PROMPT", lang), reply_markup=ReplyKeyboardRemove())
        return EDIT_DESCRIPTION

    elif action == 'editprice':
        logger.info(f"💰 Вызов функции: price_received(), ID объявления: {ann_id}")
        await query.message.reply_text(t("EDIT_PRICE_PROMPT", lang), reply_markup=ReplyKeyboardRemove())
        return EDIT_PRICE

    elif action == 'editphotos':
        logger.info(f"🖼️ Вызов функции: ask_photo_action(), ID объявления: {ann_id}")
        return await ask_photo_action(update, context)

    elif action == "edit":
        return await edit_announcement_handler(update, context)

    elif action == 'cancel':
        logger.info(f"❌ Вызов функции: cancel(), ID объявления: {ann_id}")
        return CHOOSING

    elif action == 'delete':
        logger.info(f"❌ Вызов функции: delete_announcement_by_id(), ID объявления: {ann_id}")
        await delete_announcement_by_id(ann_id, context, query)
        return CHOOSING

    elif action == 'post':
        logger.info(f"📢 Вызов функции: publish_announcement(), ID объявления: {ann_id}")
        post_link = await publish_announcement(update, context, ann_id)

        if post_link:
            await query.message.reply_text(
                t("POST_SUCCESS_MESSAGE", lang).format(post_link),
                reply_markup=get_markup(lang),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await query.message.reply_text(t("POST_FAILURE_MESSAGE", lang), reply_markup=get_markup(lang))

        return CHOOSING

async def edit_announcement_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ann_id = int(query.data.split("_")[1])
    context.user_data["ann_id"] = ann_id

    logger.info(f"✏️ [edit_announcement_handler] Открыто меню редактирования для объявления ID: {ann_id}")

    lang = get_lang(update)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("EDIT_TEXT_BUTTON", lang), callback_data=f'editdescription_{ann_id}')],
        [InlineKeyboardButton(t("EDIT_PRICE_BUTTON", lang), callback_data=f'editprice_{ann_id}')],
        [InlineKeyboardButton(t("EDIT_PHOTOS_BUTTON", lang), callback_data=f'editphotos_{ann_id}')],
        [InlineKeyboardButton(t("CANCEL_NOTHING_BUTTON", lang), callback_data=f'cancel_{ann_id}')]
    ])

    await query.message.reply_text(t("EDIT_CHOICE_TEXT", lang), reply_markup=keyboard)

    return CHOOSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    context.user_data.clear()
    await update.message.reply_text(t("CANCEL_MESSAGE", lang), reply_markup=get_markup(lang))
    return CHOOSING

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    lang = get_lang(update)
    if await is_subscribed(user_id, context):
        await query.message.reply_text(t("SUBSCRIPTION_SUCCESS", lang))
        await show_menu(update, context)
        return CHOOSING
    else:
        text, keyboard = await check_subscription_message(update)
        await query.message.reply_text(t("NOT_SUBSCRIBED_MESSAGE_SHORT", lang), reply_markup=keyboard)
        return CHECK_SUBSCRIPTION