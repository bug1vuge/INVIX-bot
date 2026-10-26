from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from redis.asyncio import Redis

from bot import texts
from bot.config import Settings
from bot.keyboards import admin_menu_keyboard, catalog_keyboard


async def send_greeting(message: Message, settings: Settings) -> None:
    private_chat = message.chat.type == "private"
    await message.answer(
        texts.GREETING,
        reply_markup=catalog_keyboard(settings.webapp_url, private_chat=private_chat),
    )

    user_id = message.from_user.id if message.from_user else None
    if private_chat and settings.is_admin(user_id):
        await message.answer(
            texts.GREETING_ADMIN_HINT.format(button=texts.CREATE_PRODUCT_BUTTON),
            reply_markup=admin_menu_keyboard(),
        )


async def start(message: Message, settings: Settings) -> None:
    await send_greeting(message, settings)


async def any_message(message: Message, settings: Settings) -> None:
    """Any other message gets the same answer as /start."""
    await send_greeting(message, settings)


async def any_album(message: Message, settings: Settings, redis: Redis) -> None:
    # Every item of an album arrives as a separate message; greet only once.
    key = f"bot:album:{message.chat.id}:{message.media_group_id}"
    if await redis.set(key, "1", nx=True, ex=60):
        await send_greeting(message, settings)


def create_router() -> Router:
    router = Router(name="common")
    router.message.register(start, CommandStart())
    router.message.register(any_album, F.chat.type == "private", F.media_group_id)
    router.message.register(any_message, F.chat.type == "private")
    return router
