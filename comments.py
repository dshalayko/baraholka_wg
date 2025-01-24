from telegram import Update
from telegram.ext import CallbackContext, MessageHandler, filters, CommandHandler, ContextTypes
from logger import logger
from config import PRIVATE_CHANNEL_ID
import sqlite3
import re
from collections import defaultdict

from utils import get_private_channel_post_link

thread_messages = defaultdict(list)
CHAT_ID = -1002212626667  # Замените на ID вашей группы



conn = sqlite3.connect("announcements.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message_id INTEGER,
    ann_id INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    message_id INTEGER,
    thread_id INTEGER,
    text TEXT,
    photo_id TEXT
)
''')

conn.commit()

def extract_ann_id(text: str) -> int:
    """Извлекает ann_id из первой строки текста как INTEGER."""
    lines = text.split('\n')
    if lines:
        match = re.search(r"#(\d+)", lines[0])
        if match:
            return int(match.group(1))
    return None


async def log_group_messages(update: Update, context: CallbackContext):
    """Логирует сообщения, удовлетворяющие условиям, и сохраняет их в базу данных."""
    try:
        if update.effective_chat.id == CHAT_ID:
            user_id = update.effective_user.id
            username = update.effective_user.username
            first_name = update.effective_user.first_name
            last_name = update.effective_user.last_name or ""
            text = update.message.text or "Нет текста"
            message_id = update.message.message_id
            thread_id = update.message.message_thread_id if update.message.message_thread_id else "Нет треда"
            ann_id = extract_ann_id(text)
            photo_id = update.message.photo[-1].file_id if update.message.photo else None

            if ann_id and message_id and user_id:
                log_text = (
                    f"[LOG] Message Info:\n"
                    f"- User ID: {user_id}\n"
                    f"- Message ID: {message_id}\n"
                    f"- Announcement ID: {ann_id}\n"
                )
                logger.info(log_text)

                with conn:
                    cursor.execute(
                        "INSERT INTO messages (user_id, message_id, ann_id) VALUES (?, ?, ?)",
                        (user_id, message_id, ann_id)
                    )

            # Если сообщение является ответом (reply) или содержит Thread ID, сохраняем в comments
            if thread_id != "Нет треда" or update.message.reply_to_message:
                log_text = (
                    f"[LOG] Message Info (Thread ID Present):\n"
                    f"- User ID: {user_id}\n"
                    f"- Username: {username}\n"
                    f"- First Name: {first_name}\n"
                    f"- Last Name: {last_name}\n"
                    f"- Message ID: {message_id}\n"
                    f"- Thread ID: {thread_id}\n"
                    f"- Text: {text}"
                    f"- Photo ID: {photo_id if photo_id else 'Нет фото'}"
                )
                logger.info(log_text)

                cursor.execute("SELECT ann_id FROM messages WHERE message_id = ?", (thread_id,))
                ann_id_result = cursor.fetchone()

                if ann_id_result:
                    ann_id = ann_id_result[0]
                    print(f"DEBUG: ann_id = {ann_id}, type = {type(ann_id)}")
                    cursor.execute("SELECT user_id, message_ids FROM announcements WHERE id = ?", (ann_id,))
                    owner = cursor.fetchone()
                    print(f"DEBUG: owner = {owner}")
                    if owner:
                        owner_id = owner[0]
                        message_ids = owner[1]

                        first_message_id = None
                        if message_ids:
                            message_ids_list = eval(message_ids) if isinstance(message_ids, str) else message_ids
                            if isinstance(message_ids_list, list) and message_ids_list:
                                first_message_id = message_ids_list[0]

                        if first_message_id:
                            announcement_link = get_private_channel_post_link(PRIVATE_CHANNEL_ID, first_message_id)
                            message_text = f"💬 Новый комментарий к вашему объявлению #{ann_id}:\n\n_{text}_\n\n🔗 [Посмотреть объявление]({announcement_link})"
                        else:
                            message_text = f"💬 Новый комментарий к вашему объявлению #{ann_id}:\n\n_{text}_"

                        if owner_id != user_id:
                            await context.bot.send_message(
                                chat_id=owner_id,
                                text=message_text,
                                parse_mode="Markdown",
                                disable_web_page_preview=True
                            )
                else:
                    logger.error(f"❌ Ошибка: Не найден ann_id по thread_id = {thread_id}.")

                parent_message_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
                with conn:
                    cursor.execute(
                        "INSERT INTO comments (user_id, username, first_name, last_name, message_id, thread_id, text, photo_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (user_id, username, first_name, last_name, message_id, thread_id if thread_id != "Нет треда" else parent_message_id, text, photo_id)
                    )
    except Exception as e:
        logger.error(f"Ошибка в log_group_messages: {e}")

async def get_thread_comments(update: Update, context: CallbackContext):
    """Выводит все комментарии из указанного треда."""
    args = context.args  # Получаем аргументы команды
    if len(args) != 1:
        await update.message.reply_text("Использование: /get_thread <thread_id>")
        return

    try:
        thread_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Ошибка: ID треда должен быть числом.")
        return

    cursor.execute("SELECT text FROM comments WHERE thread_id = ?", (thread_id,))
    comments = cursor.fetchall()

    if not comments:
        await update.message.reply_text(f"❌ Нет комментариев в треде {thread_id}.")
        return

    response = f"📜 Комментарии из треда {thread_id}:\n\n"
    for comment in comments:
        response += f"- {comment[0]}\n"

    await update.message.reply_text(response if len(response) < 4096 else "⚠️ Слишком много комментариев, вывод ограничен.")

async def reply_to_message(update: Update, context: CallbackContext):
    """Отвечает на сообщение в указанном чате по его message_id."""
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Использование: /reply <chat_id> <message_id> <текст>")
        return

    try:
        chat_id = int(args[0])
        message_id = int(args[1])
        reply_text = " ".join(args[2:])
    except ValueError:
        await update.message.reply_text("Ошибка: chat_id и message_id должны быть числами.")
        return

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=reply_text,
            reply_to_message_id=message_id  # Ответ на конкретное сообщение
        )
        await update.message.reply_text(f"✅ Ответ отправлен в чат {chat_id} на сообщение {message_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def get_chat_id(update: Update, context: CallbackContext):
    chat = update.effective_chat
    chat_type = chat.type
    chat_id = chat.id

    if chat_type in ['group', 'supergroup', 'channel']:
        await update.message.reply_text(f"Chat ID этого {chat_type}: `{chat_id}`", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"Ваш личный Chat ID: `{chat_id}`", parse_mode='Markdown')

def register_handlers(app):
    app.add_handler(MessageHandler(filters.ALL & filters.Chat(CHAT_ID), log_group_messages))
    app.add_handler(CommandHandler("get_thread", get_thread_comments, filters=filters.Chat(CHAT_ID)))
    app.add_handler(CommandHandler("reply", reply_to_message))
    app.add_handler(CommandHandler('get_chat_id', get_chat_id))