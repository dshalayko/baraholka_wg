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
    start, menu, check_subscription, handle_choice, button_handler,
    handle_add_photos, description_received, price_received, confirmation_handler,
    edit_choice_handler, edit_description_received, edit_price_received,
    cancel, error_handler, get_chat_id, relevance_button_handler, check_subscription_callback,
    menu_button_handler, show_user_announcements
)
from database import init_db
from config import (
    BOT_TOKEN, CHOOSING, ADDING_PHOTOS, DESCRIPTION, PRICE, CONFIRMATION,
    EDIT_CHOICE, EDIT_DESCRIPTION, EDIT_PRICE, CHECK_SUBSCRIPTION
)
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Обновленный ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('menu', menu),
            CallbackQueryHandler(menu_button_handler, pattern='^(add_advertisement|my_advertisements)$'),
        ],
        states={
            CHOOSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice),
                CallbackQueryHandler(button_handler, pattern=r'^(edit|delete)_\d+$'),
            ],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_received)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_received)],
            ADDING_PHOTOS: [
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_add_photos),
            ],
            CONFIRMATION: [CallbackQueryHandler(confirmation_handler, pattern='^(preview_edit|post|confirm_edit)$')],
            EDIT_CHOICE: [
                CallbackQueryHandler(edit_choice_handler, pattern='^(edit_description|edit_price|edit_photos|cancel_edit)$')
            ],
            EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_description_received)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_price_received)],
            CHECK_SUBSCRIPTION: [CallbackQueryHandler(check_subscription_callback, pattern='^check_subscription$')],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Regex('^Вернуться в меню$'), cancel)],
    )

    # Добавляем ConversationHandler
    app.add_handler(conv_handler)

    # Обработчики на верхнем уровне для команд
    app.add_handler(CommandHandler('menu', menu))
    app.add_handler(CommandHandler('get_chat_id', get_chat_id))
    app.add_handler(CallbackQueryHandler(menu_button_handler, pattern='^(add_advertisement|my_advertisements)$'))

    # Обработчики для сообщений и команд вне состояния
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r'^(edit|delete)_\d+$'))

    # Обработчик для проверки подписки
    app.add_handler(CallbackQueryHandler(check_subscription, pattern='^check_subscription$'))
    app.add_handler(CallbackQueryHandler(relevance_button_handler, pattern=r'^(extend|remove)_\d+$'))

    # Обработчик ошибок
    app.add_error_handler(error_handler)

    # Запускаем бота без удаления неподтвержденных обновлений
    await app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
