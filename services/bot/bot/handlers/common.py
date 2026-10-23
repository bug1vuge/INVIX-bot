from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot import texts
from bot.config import Settings
from bot.keyboards import admin_menu_keyboard, catalog_keyboard


async def send_greeting(message: Message, settings: Settings) -> None:
    await message.answer(texts.GREETING, reply_markup=catalog_keyboard(settings.webapp_url))

    user_id = message.from_user.id if message.from_user else None
    if message.chat.type == "private" and settings.is_admin(user_id):
        await message.answer(
            texts.GREETING_ADMIN_HINT.format(button=texts.CREATE_PRODUCT_BUTTON),
            reply_markup=admin_menu_keyboard(),
        )


async def start(message: Message, settings: Settings) -> None:
    await send_greeting(message, settings)


async def any_message(message: Message, settings: Settings) -> None:
    """Any other message gets the same answer as /start."""
    await send_greeting(message, settings)


def create_router() -> Router:
    router = Router(name="common")
    router.message.register(start, CommandStart())
    router.message.register(any_message, F.chat.type == "private")
    return router
