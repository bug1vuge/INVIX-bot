import os
from collections.abc import AsyncIterator
from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_storage
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

SERVICE_TOKEN = "test-service-token"

# CI runs the suite against PostgreSQL; locally sqlite is enough for a quick run.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


class InMemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_next_put = False

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        if self.fail_next_put:
            self.fail_next_put = False
            raise RuntimeError("storage is down")
        self.objects[key] = (body, content_type)

    async def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)

    async def ping(self) -> None:
        return None


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        environment="test",
        log_level="WARNING",
        database_url=TEST_DATABASE_URL,
        s3_endpoint_url="http://storage.invalid",
        s3_access_key="test",
        s3_secret_key="test",
        service_token=SERVICE_TOKEN,
        max_image_size_mb=1,
        page_size_default=2,
        page_size_max=5,
    )


@pytest.fixture(scope="session")
async def engine(settings: Settings):
    engine = create_async_engine(settings.database_dsn)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def sessionmaker(engine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
async def client(settings, sessionmaker, storage) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_storage] = lambda: storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def make_image(fmt: str = "JPEG", size: tuple[int, int] = (64, 48)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(200, 80, 40)).save(buffer, format=fmt)
    return buffer.getvalue()
