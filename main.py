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
    start, handle_choice, button_handler,
    cancel, error_handler,
    check_subscription_callback
)
from announcements import (
    adding_photos, description_received,
    price_received, show_user_announcements,
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
            MessageHandler(filters.TEXT, handle_choice),
            CallbackQueryHandler(handle_choice, pattern='^(add_advertisement|my_advertisements)$'),
        ],
        states={
            CHOOSING: [
                MessageHandler(filters.TEXT , handle_choice),
                CallbackQueryHandler(button_handler, pattern=r'^(editdescription|editprice|editphotos|delete|post)_\d+$'),
                CallbackQueryHandler(show_user_announcements, pattern='^my_advertisements$')
            ],
            ADDING_PHOTOS: [
                MessageHandler(filters.PHOTO | filters.TEXT, adding_photos),
            ],
            EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_received)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_received)],
            CHECK_SUBSCRIPTION: [CallbackQueryHandler(check_subscription_callback, pattern='^check_subscription$')],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
        ],
    )

    register_comment_handlers(app)
    # Добавляем ConversationHandler
    app.add_handler(conv_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler('my_ads', show_user_announcements))

    # Обработчик ошибок
    app.add_error_handler(error_handler)

    await app.run_polling(drop_pending_updates=False)


if __name__ == '__main__':
    asyncio.run(main())
