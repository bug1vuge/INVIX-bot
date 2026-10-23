from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bot import texts


def catalog_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.OPEN_CATALOG_BUTTON, web_app=WebAppInfo(url=webapp_url)
                )
            ]
        ]
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.CREATE_PRODUCT_BUTTON)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.CANCEL_BUTTON)]],
        resize_keyboard=True,
        input_field_placeholder="Фото + название в подписи",
    )
