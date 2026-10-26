from datetime import UTC, datetime

from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from tests.conftest import USER_ID

SECRET = "webhook-secret-for-tests"


def raw_update(update_id: int) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": int(datetime.now(UTC).timestamp()),
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False, "first_name": "Test"},
            "text": "/start",
        },
    }


async def make_client(app) -> TestClient:
    web_app = web.Application()
    SimpleRequestHandler(
        dispatcher=app.dispatcher, bot=app.bot, secret_token=SECRET, handle_in_background=False
    ).register(web_app, path="/bot/webhook")
    client = TestClient(TestServer(web_app))
    await client.start_server()
    return client


async def post(client: TestClient, update: dict, secret: str = SECRET):
    return await client.post(
        "/bot/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": secret}
    )


async def test_rejects_wrong_secret(app):
    client = await make_client(app)
    try:
        response = await post(client, raw_update(1), secret="wrong")
        assert response.status == 401
    finally:
        await client.close()


async def test_update_in_progress_elsewhere_returns_error(app):
    client = await make_client(app)
    try:
        await app.redis.set(f"bot:{app.bot.id}:update:7", "processing", ex=60)
        response = await post(client, raw_update(7))
        # Non-2xx makes Telegram redeliver the update later instead of dropping it.
        assert response.status == 500
        assert app.bot.session.requests == []
    finally:
        await client.close()


async def test_processed_update_is_acknowledged_once(app):
    client = await make_client(app)
    try:
        assert (await post(client, raw_update(8))).status == 200
        assert (await post(client, raw_update(8))).status == 200
        assert len(app.bot.session.sent_texts()) == 1
    finally:
        await client.close()
