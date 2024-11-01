from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton

from texts import *

# Основная клавиатура с двумя кнопками: «Добавить объявление» и «Мои объявления»
reply_keyboard = [
    ['Новое хрустящее объявление', 'Мои объявления'],
]
markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

# Клавиатура с одной кнопкой «Добавить объявление»
add_advertisement_keyboard = ReplyKeyboardMarkup(
    [['Новое хрустящее объявление']],
    resize_keyboard=True
)

# Клавиатура с кнопкой «Вернуться в меню»
cancel_keyboard = [
    [KeyboardButton('В главное меню')]
]
cancel_markup = ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True)

# Клавиатура для добавления фотографий
photo_keyboard = [
    [KeyboardButton('Объявление без фотографий')],
]
photo_markup_with_cancel = ReplyKeyboardMarkup(photo_keyboard, resize_keyboard=True)

# Клавиатура для завершения загрузки фотографий
finish_photo_keyboard = [
    [KeyboardButton(FINISH_PHOTO_UPLOAD)],
]
finish_photo_markup_with_cancel = ReplyKeyboardMarkup(finish_photo_keyboard, resize_keyboard=True)

finish_photo_markup_no_menu = ReplyKeyboardMarkup(
    [[FINISH_PHOTO_UPLOAD]],
    one_time_keyboard=True,
    resize_keyboard=True
)

# Клавиатура для редактирования
edit_keyboard = [
    [InlineKeyboardButton('Текст объявления', callback_data='edit_description')],
    [InlineKeyboardButton('Цену', callback_data='edit_price')],
    [InlineKeyboardButton('Фотографии', callback_data='edit_photos')],
    [InlineKeyboardButton('Ничего не меняем', callback_data='cancel_edit')],
]
edit_markup_with_cancel = InlineKeyboardMarkup(edit_keyboard)