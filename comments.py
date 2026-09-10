from telegram import Update
from telegram.ext import CallbackContext, MessageHandler, filters

from comments_manager import get_message_id_by_thread_id
from logger import logger
from config import CHAT_ID


from utils import  notify_owner_about_comment
from transfer_store import ensure_transfer_schema, query



async def log_group_messages(update: Update, context: CallbackContext):
    try:
        if not update.message or not update.effective_user:
            return
        user = update.effective_user
        user_id = user.id
        await ensure_transfer_schema()
        service = await query("SELECT value FROM transfer_settings WHERE key='userbot_id'", one=True)
        if service and str(user_id) == service['value']:
            return
        username = update.effective_user.username or "Нет username"
        text = update.message.text or ""
        message_id = update.message.message_id
        thread_id = update.message.message_thread_id if update.message.message_thread_id else None
        photo_id = update.message.photo[-1].file_id if update.message.photo else None

        logger.info(f"[log_group_messages] {user_id=} | {username=} | {message_id=} | {thread_id=} | {text=} | {photo_id=}")

        if user.is_bot and user.username == "GroupAnonymousBot":
            logger.info(f"🔕 [log_group_messages] Сообщение от анонимного администратора, уведомление не отправляем.")
            return

        if thread_id:
            logger.info(f"🔄 [log_group_messages] Найден thread_id={thread_id}, ищем соответствующий message_id...")
            message_id_from_thread = await get_message_id_by_thread_id(thread_id)

            if message_id_from_thread:
                logger.info(f"✅ [log_group_messages] Найден message_id={message_id_from_thread} по thread_id={thread_id}")
                await notify_owner_about_comment(context, message_id_from_thread, user_id, text)
            else:
                logger.warning(f"⚠️ [log_group_messages] Не найден message_id для thread_id={thread_id}")

    except Exception as e:
        logger.error(f"❌ [log_group_messages] Ошибка: {e}")

def register_handlers(app):
    logger.info(f"CHAT_ID: {CHAT_ID} (тип: {type(CHAT_ID)})")
    logger.info(f"✅ [register_handlers] Найден CHAT_ID={CHAT_ID}")
    # Только новые сообщения: у edited_message и прочих типов апдейтов
    # update.message == None, и обработчик падал на update.message.text.
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE & filters.Chat(int(CHAT_ID)), log_group_messages))