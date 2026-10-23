"""One-off Telegram configuration. Run it once per deploy, not per replica."""

import logging

from aiogram import Bot, Dispatcher
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    MenuButtonWebApp,
    WebAppInfo,
)

from bot import texts
from bot.config import Settings

logger = logging.getLogger(__name__)

USER_COMMANDS = [BotCommand(command="start", description="Открыть каталог")]
ADMIN_COMMANDS = [
    *USER_COMMANDS,
    BotCommand(command="create", description="Создать товар"),
    BotCommand(command="cancel", description="Отменить добавление"),
]


async def configure_bot(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> None:
    if settings.bot_mode == "webhook":
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret.get_secret_value(),
            allowed_updates=dispatcher.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        logger.info("webhook configured", extra={"url": settings.webhook_url})
    else:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("webhook removed, polling mode")

    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            # The admin has not started the bot yet; commands appear after /start.
            logger.warning("cannot set admin commands", extra={"admin_id": admin_id})

    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text=texts.MENU_BUTTON, web_app=WebAppInfo(url=settings.webapp_url)
        )
    )
    logger.info("bot configured")
