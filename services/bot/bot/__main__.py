"""Entry point.

python -m bot serve   # run a replica (webhook or polling, see BOT_MODE)
python -m bot setup   # configure webhook, commands and menu button once
"""

import argparse
import asyncio
import logging
import sys

from bot.app import create_application
from bot.config import get_settings
from bot.log_config import setup_logging
from bot.runners import run_polling, run_webhook
from bot.setup import configure_bot

logger = logging.getLogger("bot")


async def serve() -> None:
    settings = get_settings()
    app = create_application(settings)
    logger.info("bot replica starting", extra={"mode": settings.bot_mode})
    try:
        if settings.bot_mode == "webhook":
            await run_webhook(app, settings)
        else:
            await run_polling(app, settings)
    finally:
        await app.close()
        logger.info("bot replica stopped")


async def setup() -> None:
    settings = get_settings()
    app = create_application(settings)
    try:
        await configure_bot(app.bot, app.dispatcher, settings)
    finally:
        await app.close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="bot")
    parser.add_argument("command", choices=("serve", "setup"))
    args = parser.parse_args()

    setup_logging(get_settings().log_level)
    asyncio.run(serve() if args.command == "serve" else setup())
    return 0


if __name__ == "__main__":
    sys.exit(main())
