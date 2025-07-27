from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton

from texts import *

# Основная клавиатура с двумя кнопками: «Добавить объявление» и «Мои объявления»
reply_keyboard = [
    [NEW_AD_CHOICE, MY_ADS_CHOICE],
]
markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

# Клавиатура с одной кнопкой «Добавить объявление»
add_advertisement_keyboard = ReplyKeyboardMarkup(
    [[NEW_AD_CHOICE]],
    resize_keyboard=True
)

# Клавиатура с кнопкой «Вернуться в меню»
cancel_keyboard = [
    [KeyboardButton(MAIN_MENU_BUTTON)]
]
cancel_markup = ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True)

# Клавиатура для добавления фотографий
photo_keyboard = [
    [KeyboardButton(NO_PHOTO_AD)],
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
