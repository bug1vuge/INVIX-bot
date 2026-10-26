import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

PROCESSING = b"processing"


class UpdateInProgressError(Exception):
    """Another replica has claimed the update and has not finished it yet.

    Raised instead of silently skipping: the webhook then answers with an
    error and Telegram redelivers the update later. If the replica that
    claimed it has died, the claim expires and the redelivery is handled.
    """


class UpdateDeduplicationMiddleware(BaseMiddleware):
    """Makes sure every update is handled once across all replicas.

    Telegram redelivers an update if the webhook call times out or fails, and
    the retry may land on a different replica. The first replica to claim the
    update id in Redis handles it; the claim is released on failure so that a
    redelivery can be processed again.
    """

    def __init__(self, redis: Redis, processing_ttl: int = 60, done_ttl: int = 86400) -> None:
        self._redis = redis
        self._processing_ttl = processing_ttl
        self._done_ttl = done_ttl

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        bot = data["bot"]
        key = f"bot:{bot.id}:update:{event.update_id}"

        claimed = await self._redis.set(key, "processing", nx=True, ex=self._processing_ttl)
        if not claimed:
            if await self._redis.get(key) == PROCESSING:
                logger.warning(
                    "update is being handled elsewhere", extra={"update_id": event.update_id}
                )
                raise UpdateInProgressError(event.update_id)
            logger.info("duplicate update skipped", extra={"update_id": event.update_id})
            return None

        try:
            result = await handler(event, data)
        except BaseException:
            await self._redis.delete(key)
            raise

        await self._redis.set(key, "done", ex=self._done_ttl)
        return result
