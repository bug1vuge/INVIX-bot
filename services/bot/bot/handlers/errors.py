import logging

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent
from redis.exceptions import RedisError

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
    # These must reach the webhook handler: Telegram then gets an error
    # response and redelivers the update later instead of it being lost
    # (another replica is still handling it, or Redis is unavailable).
    router.errors.register(log_error, ~ExceptionTypeFilter(UpdateInProgressError, RedisError))
    return router
