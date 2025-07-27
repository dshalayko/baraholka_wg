from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton

from texts import t


def get_markup(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[t("NEW_AD_CHOICE", lang), t("MY_ADS_CHOICE", lang)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_add_advertisement_keyboard(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[t("NEW_AD_CHOICE", lang)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_cancel_markup(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(t("MAIN_MENU_BUTTON", lang))]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_photo_markup_with_cancel(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(t("NO_PHOTO_AD", lang))]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_finish_photo_markup_with_cancel(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(t("FINISH_PHOTO_UPLOAD", lang))]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_finish_photo_markup_no_menu(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[t("FINISH_PHOTO_UPLOAD", lang)]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
