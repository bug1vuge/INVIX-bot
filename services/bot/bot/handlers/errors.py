import logging

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent

from bot.middlewares.deduplication import UpdateInProgressError

logger = logging.getLogger(__name__)


async def log_error(event: ErrorEvent) -> bool:
    logger.error(
        "update handling failed",
        extra={"update_id": event.update.update_id},
        exc_info=event.exception,
    )
    return True


def create_router() -> Router:
    router = Router(name="errors")
    # UpdateInProgressError must reach the webhook handler so that Telegram
    # gets an error response and redelivers the update later.
    router.errors.register(log_error, ~ExceptionTypeFilter(UpdateInProgressError))
    return router
