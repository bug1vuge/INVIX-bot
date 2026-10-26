import asyncio
import contextlib
import logging
import signal
import uuid

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis
from redis.exceptions import RedisError

from bot.app import Application
from bot.config import Settings

logger = logging.getLogger(__name__)

LEADER_TTL_SECONDS = 15
LEADER_RETRY_SECONDS = 5

# Extend / release the leader key only if this instance still owns it.
_EXTEND_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('pexpire', KEYS[1], ARGV[2])
end
return 0
"""
_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def _install_stop_signals(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)


def _health_routes(app: Application) -> list[web.RouteDef]:
    async def live(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def ready(_: web.Request) -> web.Response:
        try:
            await asyncio.wait_for(app.redis.ping(), timeout=3)
        except (RedisError, TimeoutError, OSError):
            return web.json_response({"status": "fail", "checks": {"redis": "fail"}}, status=503)
        return web.json_response({"status": "ok", "checks": {"redis": "ok"}})

    return [web.get("/health/live", live), web.get("/health/ready", ready)]


async def _serve(web_app: web.Application, settings: Settings, stop: asyncio.Event) -> None:
    runner = web.AppRunner(web_app, handle_signals=False, access_log=None, shutdown_timeout=20)
    await runner.setup()
    site = web.TCPSite(runner, settings.server_host, settings.server_port)
    await site.start()
    logger.info("http server started", extra={"port": settings.server_port})
    try:
        await stop.wait()
    finally:
        await runner.cleanup()


async def run_webhook(app: Application, settings: Settings) -> None:
    """Every replica accepts webhook calls; the gateway spreads them."""
    stop = asyncio.Event()
    _install_stop_signals(stop)

    web_app = web.Application()
    web_app.add_routes(_health_routes(app))

    SimpleRequestHandler(
        dispatcher=app.dispatcher,
        bot=app.bot,
        secret_token=settings.webhook_secret.get_secret_value(),
        # Answer Telegram only after the update is handled: if this replica
        # dies mid-way, Telegram redelivers the update to another one.
        handle_in_background=False,
    ).register(web_app, path=settings.webhook_path)
    setup_application(web_app, app.dispatcher, bot=app.bot)

    await _serve(web_app, settings, stop)


async def run_polling(app: Application, settings: Settings) -> None:
    """Long polling with leader election.

    Telegram allows a single getUpdates consumer per bot, so replicas compete
    for a Redis key: the owner polls, the others stay on hot standby and take
    over within LEADER_TTL_SECONDS if the leader goes away.
    """
    stop = asyncio.Event()
    _install_stop_signals(stop)

    web_app = web.Application()
    web_app.add_routes(_health_routes(app))
    server = asyncio.create_task(_serve(web_app, settings, stop))

    instance_id = uuid.uuid4().hex
    leader_key = f"bot:{app.bot.id}:polling-leader"

    try:
        while not stop.is_set():
            if await _try_acquire(app.redis, leader_key, instance_id):
                logger.info("acquired polling leadership", extra={"instance": instance_id})
                await _poll_while_leader(app, leader_key, instance_id, stop)
                logger.info("released polling leadership", extra={"instance": instance_id})
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=LEADER_RETRY_SECONDS)
    finally:
        stop.set()
        await server


async def _try_acquire(redis: Redis, key: str, instance_id: str) -> bool:
    try:
        return bool(await redis.set(key, instance_id, nx=True, ex=LEADER_TTL_SECONDS))
    except RedisError:
        logger.warning("redis is unavailable, cannot elect polling leader", exc_info=True)
        return False


async def _hold_leadership(redis: Redis, key: str, instance_id: str) -> None:
    """Returns as soon as leadership can no longer be guaranteed."""
    interval = LEADER_TTL_SECONDS / 3
    while True:
        await asyncio.sleep(interval)
        try:
            extended = await redis.eval(
                _EXTEND_SCRIPT, 1, key, instance_id, LEADER_TTL_SECONDS * 1000
            )
        except RedisError:
            logger.warning("failed to extend polling leadership", exc_info=True)
            return
        if not extended:
            logger.warning("polling leadership lost")
            return


async def _poll_while_leader(
    app: Application, key: str, instance_id: str, stop: asyncio.Event
) -> None:
    try:
        await app.bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        # Telegram is unreachable: give the leadership back and try again later.
        logger.warning("cannot remove webhook before polling", exc_info=True)
        with contextlib.suppress(RedisError):
            await app.redis.eval(_RELEASE_SCRIPT, 1, key, instance_id)
        return

    polling = asyncio.create_task(
        app.dispatcher.start_polling(app.bot, handle_signals=False, close_bot_session=False)
    )
    holder = asyncio.create_task(_hold_leadership(app.redis, key, instance_id))
    stopper = asyncio.create_task(stop.wait())

    await asyncio.wait({polling, holder, stopper}, return_when=asyncio.FIRST_COMPLETED)

    if not polling.done():
        with contextlib.suppress(RuntimeError):
            await app.dispatcher.stop_polling()
    for task in (holder, stopper):
        task.cancel()

    try:
        await polling
    except Exception:
        logger.exception("polling stopped with an error")

    with contextlib.suppress(RedisError):
        await app.redis.eval(_RELEASE_SCRIPT, 1, key, instance_id)
