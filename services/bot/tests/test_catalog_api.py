import httpx
import pytest

from bot.services.catalog_api import CatalogApiError, CatalogClient, CatalogUnavailableError


def client_with(handler) -> CatalogClient:
    return CatalogClient(
        base_url="http://api",
        service_token="secret",
        backoff=0,
        transport=httpx.MockTransport(handler),
    )


def created(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201, json={"id": "p1", "name": "Стул", "image_url": "/media/products/p1.jpg"}
    )


async def test_sends_auth_and_idempotency_key():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return created(request)

    client = client_with(handler)
    product = await client.create_product(
        name="Стул", image=b"img", filename="a.jpg", idempotency_key="tg:1:2", created_by=7
    )

    assert product.id == "p1"
    request = seen[0]
    assert request.headers["authorization"] == "Bearer secret"
    assert request.headers["idempotency-key"] == "tg:1:2"
    assert b'name="name"' in request.content
    await client.close()


async def test_retries_transient_failures():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("refused")
        if attempts == 2:
            return httpx.Response(503, json={"error": {"code": "x", "message": "busy"}})
        return created(request)

    client = client_with(handler)
    await client.create_product(name="Стул", image=b"img", filename="a.jpg", idempotency_key="k")
    assert attempts == 3


async def test_does_not_retry_client_errors():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            422, json={"error": {"code": "invalid_image", "message": "File is not a valid image"}}
        )

    client = client_with(handler)
    with pytest.raises(CatalogApiError) as exc_info:
        await client.create_product(name="Стул", image=b"x", filename="a.jpg", idempotency_key="k")

    assert attempts == 1
    assert exc_info.value.code == "invalid_image"


async def test_gives_up_after_all_attempts():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = client_with(handler)
    with pytest.raises(CatalogUnavailableError):
        await client.create_product(name="Стул", image=b"x", filename="a.jpg", idempotency_key="k")
