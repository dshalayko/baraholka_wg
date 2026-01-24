from telegram import ReplyKeyboardMarkup, KeyboardButton

import texts as texts_ru
import texts_en


def _texts_for_language(language_code: str | None):
    if language_code and not language_code.lower().startswith("ru"):
        return texts_en
    return texts_ru


def get_main_markup(language_code: str | None):
    texts = _texts_for_language(language_code)
    reply_keyboard = [
        [texts.NEW_AD_CHOICE, texts.MY_ADS_CHOICE],
    ]
    return ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)


def get_add_advertisement_keyboard(language_code: str | None):
    texts = _texts_for_language(language_code)
    return ReplyKeyboardMarkup(
        [[texts.NEW_AD_CHOICE]],
        resize_keyboard=True
    )


def get_cancel_markup(language_code: str | None):
    texts = _texts_for_language(language_code)
    cancel_keyboard = [
        [KeyboardButton(texts.MAIN_MENU_BUTTON)]
    ]
    return ReplyKeyboardMarkup(cancel_keyboard, resize_keyboard=True)


def get_photo_markup_with_cancel(language_code: str | None):
    texts = _texts_for_language(language_code)
    photo_keyboard = [
        [KeyboardButton(texts.NO_PHOTO_AD)],
    ]
    return ReplyKeyboardMarkup(photo_keyboard, resize_keyboard=True)


def get_finish_photo_markup_with_cancel(language_code: str | None):
    texts = _texts_for_language(language_code)
    finish_photo_keyboard = [
        [KeyboardButton(texts.FINISH_PHOTO_UPLOAD)],
    ]
    return ReplyKeyboardMarkup(finish_photo_keyboard, resize_keyboard=True)


def get_finish_photo_markup_no_menu(language_code: str | None):
    texts = _texts_for_language(language_code)
    return ReplyKeyboardMarkup(
        [[texts.FINISH_PHOTO_UPLOAD]],
        one_time_keyboard=True,
        resize_keyboard=True
    )
