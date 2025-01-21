from telegram import Update
from telegram.ext import CallbackContext, MessageHandler, filters, CommandHandler
from logger import logger
import sqlite3
from collections import defaultdict
thread_messages = defaultdict(list)
CHAT_ID = -1002212626667  # Замените на ID вашей группы


# Создаем базу данных и таблицы
conn = sqlite3.connect("announcements.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    message_id INTEGER,
    thread_id TEXT,
    text TEXT
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
    thread_id TEXT,
    text TEXT
)
''')

conn.commit()

async def log_group_messages(update: Update, context: CallbackContext):
    """Логирует сообщения, удовлетворяющие определенным условиям и сохраняет их в базу данных."""
    if update.effective_chat.id == CHAT_ID:
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name or ""
        text = update.message.text or "Нет текста"
        message_id = update.message.message_id
        thread_id = update.message.message_thread_id if update.message.message_thread_id else "Нет треда"

        # Условие логирования: First Name: Telegram и Нет треда
        if first_name == "Telegram" and username is None and last_name == "" and thread_id == "Нет треда":
            log_text = (
                f"[LOG] Message Info (No Thread):\n"
                f"- User ID: {user_id}\n"
                f"- Username: {username}\n"
                f"- First Name: {first_name}\n"
                f"- Last Name: {last_name}\n"
                f"- Message ID: {message_id}\n"
                f"- Thread ID: {thread_id}\n"
                f"- Text: {text}"
            )
            logger.info(log_text)

            # Сохраняем в базу данных
            cursor.execute(
                "INSERT INTO messages (user_id, username, first_name, last_name, message_id, thread_id, text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, first_name, last_name, message_id, thread_id, text)
            )
            conn.commit()

        # Условие логирования: Сообщения с Thread ID
        if thread_id != "Нет треда":
            log_text = (
                f"[LOG] Message Info (Thread ID Present):\n"
                f"- User ID: {user_id}\n"
                f"- Username: {username}\n"
                f"- First Name: {first_name}\n"
                f"- Last Name: {last_name}\n"
                f"- Message ID: {message_id}\n"
                f"- Thread ID: {thread_id}\n"
                f"- Text: {text}"
            )
            logger.info(log_text)

            # Сохраняем в базу данных как комментарий
            cursor.execute(
                "INSERT INTO comments (user_id, username, first_name, last_name, message_id, thread_id, text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, first_name, last_name, message_id, thread_id, text)
            )
            conn.commit()

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

    cursor.execute("SELECT text FROM comments WHERE thread_id = ?", (str(thread_id),))
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

def register_handlers(app):
    app.add_handler(MessageHandler(filters.ALL & filters.Chat(CHAT_ID), log_group_messages))
    app.add_handler(CommandHandler("get_thread", get_thread_comments))
    app.add_handler(CommandHandler("reply", reply_to_message))
