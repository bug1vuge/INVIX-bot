import logging

from aiogram import Router
from aiogram.types import ErrorEvent

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
    router.errors.register(log_error)
    return router
