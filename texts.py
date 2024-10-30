# Общие текстовые переменные
WELCOME_NEW_USER = "Привет! Я — бот-барахольщик канала WG Black Market. Я буду постить объявления от вашего имени, а если в будущем вы захотите что-то изменить или снять с публикации, это тоже ко мне."
START_NEW_AD = "Пришлите текст объявления. Дальше я попрошу указать цену и добавить фотографии. Но в первую очередь — расскажите, что вы хотите продать или купить."
CHOOSE_ACTION = "Пожалуйста, выберите действие с помощью кнопок."
NEW_AD_CHOICE = "Новое хрустящее объявление"
MY_ADS_CHOICE = "Мои объявления"
PREVIEW_LOADING = "Ожидайте предварительный просмотр."
PREVIEW_TEXT = "Вот как это будет выглядеть."
EDIT = "Редактировать"
POST = "Опубликовать"
SUBSCRIPTION_SUCCESS = "Спасибо за подписку! 💃🏻"
NOT_SUBSCRIBED_YET = "Вы еще не подписались на канал. Пожалуйста, подпишитесь и нажмите 'Я подписался'."
DESC_PRICE_REQUIRED = "❗Описание и цена обязательны для создания объявления."
ADD_PHOTO_TEXT = "Фото поймал! Можете добавить ещё, если хотите."
SEND_PHOTO_OR_FINISH = "Пожалуйста, отправьте фотографию."
SEND_PHOTO_OR_FINISH_OR_NO_PHOTO = "Пожалуйста, отправьте фотографию либо нажмите 'Объявление без фотографий'."
MAX_PHOTOS_REACHED = "Вы можете загрузить не более 10 фотографий. Лишние фото не будут сохранены."
PHOTO_ADDED_LOG = "Добавлено фото:"
PHOTO_UPLOAD_FINISHED_LOG = "Пользователь завершил загрузку фото."
ADDING_PHOTOS_STARTED_LOG = "Начало функции добавления фотографий."
NO_PHOTO_AD = "Объявление без фотографий"
NO_PHOTO_ACCEPTED = "Ну, без фотографий, так без фотографий."
NO_PHOTO_CHOSEN_LOG = "Пользователь выбрал создание объявления без фото."
PROCESSING_PHOTOS = "Обработка фотографий"
DELETE_OLD_MESSAGE_ERROR = "Ошибка при удалении старого сообщения"
EDITING_AD_LOG = "Редактирование объявления с ID:"
DESC_PRICE_FETCHED_LOG = "Загруженные описание и цена из базы:"
AD_NOT_FOUND = "Не удалось найти объявление для редактирования."
PRICE_TEXT = "*Цена*"
CONTACT_TEXT = "*Кому писать*"
UPDATED_TEXT = "🆙 _Обновлено {current_time}_"
FINISH_PHOTO_UPLOAD = "С фото закончили, давайте дальше"
MAIN_MENU = "В главное меню"
EDIT_PROMPT = "Что меняем?"
POST_SUCCESS_MESSAGE = "💥 *Успех! Вот ссылка на ваше объявление:*\n{}\n\n_Кстати, за комментариями к постам я не слежу, так что заглядывайте внутрь своих объявлений самостоятельно._"
POST_FAILURE_MESSAGE = "Произошла ошибка при размещении объявления."
EDIT_DESCRIPTION_PROMPT = "Не вопрос. Присылайте новый текст объявления."
EDIT_PRICE_PROMPT = "Ок! Какой будет новая цена?"
EDIT_PHOTOS_PROMPT = "Легко! Присылайте новые фотографии.\n\nЕсли нужно удалить, сразу нажмите «С фото закончили», тогда все приложенные я уберу."
ANNOUNCEMENT_MESSAGE = "Автор: @{username}\n{description}\n\n*Цена*\n{price}"
DELETE_SUCCESS_MESSAGE = "Ваше объявление было удалено."
NO_ANNOUNCEMENTS_MESSAGE = "У вас пока нет объявлений."
ANNOUNCEMENT_LIST_MESSAGE = "{description}\n\n*Цена*\n{price}"
FULL_VERSION_MESSAGE = "➡️ Ссылка на объявление"
DELETE_BUTTON = "Удалить"
CANCEL_MESSAGE = "Ок, отменили."
GROUP_CHAT_ID_MESSAGE = "Chat ID этого {chat_type}: `{chat_id}`"
USER_CHAT_ID_MESSAGE = "Ваш личный Chat ID: `{chat_id}`"
ERROR_LOG = "Exception while handling an update:"
ASK_FOR_PHOTOS = "А теперь — фото! Можно сразу несколько.\n\n_Хайрезы я не принимаю, поэтому не убирайте галочку с настройки «Сжимать фотографии»._"
RELEVANCE_CHECK_MESSAGE = "Ваше объявление скоро устареет. Хотите продлить или удалить его?"
EXTEND_BUTTON = "Продлить"
REMOVE_BUTTON = "Удалить"
EXTENDED_MESSAGE = "Ваше объявление было продлено на 2 недели."

# Ошибки
LONG_PRICE_ERROR = "❗Цена слишком длинная. Максимум 255 символов. Сейчас: {} символов."
EMPTY_PRICE_ERROR = "❗Цена не может быть пустой. Пожалуйста, введите цену."
EMPTY_DESCRIPTION_ERROR = "Описание не может быть пустым. Пожалуйста, введите описание."
ANNOUNCEMENT_NOT_FOUND = "Не удалось найти объявление для редактирования."
AD_NOT_FOUND_ERROR = "Не удалось найти объявление с ID {}."
SEND_MESSAGE_ERROR = "Ошибка при отправке сообщения пользователю: {}"
DELETE_MESSAGE_ERROR = "Ошибка при удалении сообщения из канала: {}"

# Логи
CONFIRMATION_HANDLER_LOG = "Начало функции confirmation_handler с данными: {}"
USER_POST_CHOICE = "Пользователь выбрал размещение объявления."
EDIT_ANNOUNCEMENT_LOG = "Редактируемое объявление ID: {}"
NEW_ANNOUNCEMENT_LOG = "Новое объявление, создание с нуля."
DELETE_SUCCESS_LOG = "Сообщение с ID {} удалено из канала."
DELETE_ERROR_LOG = "Ошибка при удалении сообщения {}: {}"
USER_MESSAGE_DELETE_LOG = "Сообщение с объявлением у пользователя удалено."
USER_MESSAGE_DELETE_ERROR_LOG = "Ошибка при удалении сообщения у пользователя: {}"



# Константы
MAX_MESSAGE_LENGTH = 1024

