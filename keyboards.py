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


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Keyboard with a single button to confirm subscription."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(I_SUBSCRIBED_BUTTON, callback_data="check_subscription")]]
    )


def get_photo_action_keyboard(ann_id: int) -> InlineKeyboardMarkup:
    """Keyboard asking how to handle existing photos."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ADD_TO_OLD_PHOTOS, callback_data=f"addphotos_{ann_id}")],
            [InlineKeyboardButton(REPLACE_ALL_PHOTOS, callback_data=f"replacephotos_{ann_id}")],
            [InlineKeyboardButton(SKIP_ADD_PHOTOS, callback_data=f"cancel_photo_{ann_id}")],
        ]
    )


def get_preview_keyboard(ann_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown on preview with edit and publish buttons."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(EDIT_BUTTON, callback_data=f"edit_{ann_id}")],
            [InlineKeyboardButton(PUBLISH_BUTTON, callback_data=f"post_{ann_id}")],
        ]
    )


def get_edit_delete_keyboard(ann_id: int) -> InlineKeyboardMarkup:
    """Keyboard with edit and delete buttons for user's ads list."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(EDIT_BUTTON, callback_data=f"edit_{ann_id}"),
                InlineKeyboardButton(DELETE_BUTTON, callback_data=f"delete_{ann_id}"),
            ]
        ]
    )


def get_edit_menu_keyboard(ann_id: int) -> InlineKeyboardMarkup:
    """Keyboard for the edit announcement menu."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(EDIT_TEXT_BUTTON, callback_data=f"editdescription_{ann_id}")],
            [InlineKeyboardButton(EDIT_PRICE_BUTTON, callback_data=f"editprice_{ann_id}")],
            [InlineKeyboardButton(EDIT_PHOTOS_BUTTON, callback_data=f"editphotos_{ann_id}")],
            [InlineKeyboardButton(CANCEL_NOTHING_BUTTON, callback_data=f"cancel_{ann_id}")],
        ]
    )

