import asyncio
import nest_asyncio

nest_asyncio.apply()

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
)
from handlers import (
    start, menu, handle_choice, button_handler,
    cancel, error_handler, get_chat_id,
    menu_button_handler, check_subscription_callback
)
from announcements import (
    create_announcement, adding_photos, description_received,
    price_received, show_user_announcements, publish_announcement,
    delete_announcement_by_id
)
from comments import register_handlers as register_comment_handlers
from database import init_db
from config import (
    BOT_TOKEN, CHOOSING, ADDING_PHOTOS, CHECK_SUBSCRIPTION, EDIT_DESCRIPTION, EDIT_PRICE
)


async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('menu', menu),
            CallbackQueryHandler(menu_button_handler, pattern='^(add_advertisement|my_advertisements)$'),
        ],
        states={
            CHOOSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice),
                CallbackQueryHandler(button_handler,
                                     pattern=r'^(editdescription|editprice|editphotos|delete|up|post)_\d+$'),
                CallbackQueryHandler(show_user_announcements, pattern='^my_advertisements$')
            ],
            ADDING_PHOTOS: [
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, adding_photos),
            ],
            EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_received)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_received)],
            CHECK_SUBSCRIPTION: [CallbackQueryHandler(check_subscription_callback, pattern='^check_subscription$')],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Regex('^Вернуться в меню$'), cancel)],
    )

    # Добавляем ConversationHandler
    app.add_handler(conv_handler)

    # Обработчики на верхнем уровне для команд
    app.add_handler(CommandHandler('menu', menu))
    app.add_handler(CommandHandler('get_chat_id', get_chat_id))
    app.add_handler(CommandHandler('my_ads', show_user_announcements))  # ОСТАВИЛИ, если нужно вызывать через /my_ads

    # Регистрируем обработчики комментариев
    register_comment_handlers(app)

    # Обработчик ошибок
    app.add_error_handler(error_handler)

    # Запускаем бота без удаления неподтвержденных обновлений
    await app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    asyncio.run(main())
