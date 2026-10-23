from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.config import Settings


class IsAdmin(BaseFilter):
    async def __call__(self, message: Message, settings: Settings) -> bool:
        return message.from_user is not None and settings.is_admin(message.from_user.id)
