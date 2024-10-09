from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton

# Основная клавиатура с двумя кнопками: «Добавить объявление» и «Мои объявления»
reply_keyboard = [
    ['Добавить объявление', 'Мои объявления'],
]
markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

# Клавиатура с одной кнопкой «Добавить объявление»
add_advertisement_keyboard = ReplyKeyboardMarkup(
    [['Добавить объявление']],
    resize_keyboard=True
)

# Клавиатура с кнопкой «Вернуться в меню»
cancel_keyboard = [
    [KeyboardButton('Вернуться в меню')]
]
cancel_markup = ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True)

# Клавиатура для добавления фотографий
photo_keyboard = [
    [KeyboardButton('Объявление без фото')],
    [KeyboardButton('Вернуться в меню')]
]
photo_markup_with_cancel = ReplyKeyboardMarkup(photo_keyboard, resize_keyboard=True)

# Клавиатура для завершения загрузки фотографий
finish_photo_keyboard = [
    [KeyboardButton('Закончить загрузку фото')],
    [KeyboardButton('Вернуться в меню')]
]
finish_photo_markup_with_cancel = ReplyKeyboardMarkup(finish_photo_keyboard, resize_keyboard=True)

# Клавиатура для редактирования
edit_keyboard = [
    [InlineKeyboardButton('Описание', callback_data='edit_description')],
    [InlineKeyboardButton('Цена', callback_data='edit_price')],
    [InlineKeyboardButton('Фото', callback_data='edit_photos')],
    [InlineKeyboardButton('Отмена', callback_data='cancel_edit')],
]
edit_markup_with_cancel = InlineKeyboardMarkup(edit_keyboard)