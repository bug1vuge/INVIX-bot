from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bot import texts


def catalog_keyboard(webapp_url: str, *, private_chat: bool = True) -> InlineKeyboardMarkup:
    # Telegram allows web_app buttons only in private chats; elsewhere the
    # catalog opens as a regular link.
    if private_chat:
        button = InlineKeyboardButton(
            text=texts.OPEN_CATALOG_BUTTON, web_app=WebAppInfo(url=webapp_url)
        )
    else:
        button = InlineKeyboardButton(text=texts.OPEN_CATALOG_BUTTON, url=webapp_url)
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


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
