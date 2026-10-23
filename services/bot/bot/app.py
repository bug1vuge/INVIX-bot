from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.config import Settings
from bot.handlers import build_router
from bot.middlewares.deduplication import UpdateDeduplicationMiddleware
from bot.services.catalog_api import CatalogClient

FSM_TTL_SECONDS = 60 * 60


@dataclass(slots=True)
class Application:
    bot: Bot
    dispatcher: Dispatcher
    redis: Redis
    catalog: CatalogClient

    async def close(self) -> None:
        await self.catalog.close()
        # RedisStorage owns the shared Redis client and closes it as well.
        await self.dispatcher.storage.close()
        await self.bot.session.close()


def create_bot(settings: Settings) -> Bot:
    session = None
    if settings.telegram_api_url:
        session = AiohttpSession(api=TelegramAPIServer.from_base(settings.telegram_api_url))
    return Bot(
        token=settings.bot_token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_application(
    settings: Settings,
    *,
    bot: Bot | None = None,
    redis: Redis | None = None,
    catalog: CatalogClient | None = None,
) -> Application:
    """Wire the bot. Nothing here is kept in process memory between updates:
    FSM state and deduplication markers live in Redis, products in the API.
    """
    redis = redis or Redis.from_url(settings.redis_url, health_check_interval=30)
    storage = RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(with_bot_id=True),
        state_ttl=FSM_TTL_SECONDS,
        data_ttl=FSM_TTL_SECONDS,
    )
    catalog = catalog or CatalogClient(
        base_url=settings.api_base_url,
        service_token=settings.service_token.get_secret_value(),
        timeout=settings.api_timeout,
    )

    dispatcher = Dispatcher(
        storage=storage,
        settings=settings,
        catalog=catalog,
        redis=redis,
    )
    dispatcher.update.outer_middleware(UpdateDeduplicationMiddleware(redis, processing_ttl=60))
    dispatcher.include_router(build_router())

    return Application(
        bot=bot or create_bot(settings),
        dispatcher=dispatcher,
        redis=redis,
        catalog=catalog,
    )
