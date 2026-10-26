from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetFile, SendChatAction, TelegramMethod
from aiogram.types import Chat, File, Message, PhotoSize, Update, User
from fakeredis import FakeAsyncRedis

from bot.app import Application, create_application
from bot.config import Settings
from bot.services.catalog_api import CreatedProduct

ADMIN_ID = 1001
USER_ID = 2002
BOT_TOKEN = "123456:TEST-token-for-unit-tests"
PHOTO_BYTES = b"\xff\xd8\xff fake jpeg"


class RecordingSession(BaseSession):
    """Answers Bot API calls locally and keeps them for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod] = []
        self._message_id = 500
        self.fail_downloads = False

    async def close(self) -> None:
        return None

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None):  # noqa: ASYNC109
        self.requests.append(method)
        if isinstance(method, SendChatAction):
            return True
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_path="photos/p.jpg")
        self._message_id += 1
        return Message(
            message_id=self._message_id,
            date=datetime.now(UTC),
            chat=Chat(id=getattr(method, "chat_id", 0), type="private"),
            text=getattr(method, "text", None),
        )

    async def stream_content(
        self,
        url,
        headers=None,
        timeout=30,  # noqa: ASYNC109
        chunk_size=65536,
        raise_for_status=True,
    ):
        if self.fail_downloads:
            raise TelegramNetworkError(method=GetFile(file_id="x"), message="connection reset")
        yield PHOTO_BYTES

    def sent_texts(self) -> list[str]:
        return [m.text for m in self.requests if getattr(m, "text", None)]


class FakeCatalog:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    async def create_product(self, **kwargs: Any) -> CreatedProduct:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return CreatedProduct(id="p1", name=kwargs["name"], image_url="/media/products/p1.jpg")

    async def close(self) -> None:
        return None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        bot_token=BOT_TOKEN,
        admin_ids=str(ADMIN_ID),
        service_token="service",
        webapp_url="https://shop.example.com/",
        bot_mode="polling",
    )


@pytest.fixture
async def app(settings) -> AsyncGenerator[Application]:
    redis = FakeAsyncRedis()
    application = create_application(
        settings,
        bot=Bot(token=BOT_TOKEN, session=RecordingSession()),
        redis=redis,
        catalog=FakeCatalog(),  # type: ignore[arg-type]
    )
    yield application
    await redis.aclose()


class UpdateFactory:
    def __init__(self) -> None:
        self._update_id = 0
        self._message_id = 0

    def message(self, user_id: int, chat_type: str = "private", **fields: Any) -> Update:
        self._update_id += 1
        self._message_id += 1
        user = User(id=user_id, is_bot=False, first_name="Test")
        chat_id = user_id if chat_type == "private" else -100500
        message = Message(
            message_id=self._message_id,
            date=datetime.now(UTC),
            chat=Chat(id=chat_id, type=chat_type),
            from_user=user,
            **fields,
        )
        return Update(update_id=self._update_id, message=message)

    def photo(self, user_id: int, caption: str | None = None, **fields: Any) -> Update:
        sizes = [
            PhotoSize(file_id="small", file_unique_id="s", width=90, height=90, file_size=1000),
            PhotoSize(file_id="large", file_unique_id="l", width=1280, height=960, file_size=90000),
        ]
        return self.message(user_id, photo=sizes, caption=caption, **fields)


@pytest.fixture
def updates() -> UpdateFactory:
    return UpdateFactory()


async def feed(app: Application, update: Update) -> None:
    await app.dispatcher.feed_update(app.bot, update)
