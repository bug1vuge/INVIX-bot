from tests.conftest import make_image


async def create(client, headers, name="Кружка", image=None, key=None):
    if key:
        headers = {**headers, "Idempotency-Key": key}
    return await client.post(
        "/api/v1/products",
        headers=headers,
        data={"name": name, "created_by": "42"},
        files={"image": ("photo.jpg", image or make_image(), "image/jpeg")},
    )


async def test_create_product(client, auth_headers, storage):
    response = await create(client, auth_headers, name="  Кружка   керамическая ")

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Кружка керамическая"
    assert body["image_width"] == 64
    assert body["image_height"] == 48
    assert body["image_url"].startswith("/media/products/")
    assert body["image_url"].endswith(".jpg")

    key = body["image_url"].removeprefix("/media/")
    assert storage.objects[key][1] == "image/jpeg"


async def test_create_requires_service_token(client):
    response = await create(client, {"Authorization": "Bearer wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"

    response = await create(client, {})
    assert response.status_code == 401


async def test_create_detects_format_from_bytes(client, auth_headers, storage):
    # Declared as JPEG, actually PNG: the stored content type must be PNG.
    response = await create(client, auth_headers, image=make_image("PNG"))

    assert response.status_code == 201
    key = response.json()["image_url"].removeprefix("/media/")
    assert key.endswith(".png")
    assert storage.objects[key][1] == "image/png"


async def test_create_rejects_non_image(client, auth_headers, storage):
    response = await create(client, auth_headers, image=b"definitely not an image")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_image"
    assert storage.objects == {}


async def test_create_rejects_unsupported_format(client, auth_headers):
    response = await create(client, auth_headers, image=make_image("GIF"))
    assert response.status_code == 422


async def test_create_rejects_large_image(client, auth_headers):
    response = await create(client, auth_headers, image=b"\xff" * (1024 * 1024 + 10))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "image_too_large"


async def test_create_rejects_blank_name(client, auth_headers):
    response = await create(client, auth_headers, name="   ")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_name"


async def test_create_rejects_long_name(client, auth_headers):
    response = await create(client, auth_headers, name="x" * 256)
    assert response.status_code == 422


async def test_idempotent_create(client, auth_headers, storage):
    first = await create(client, auth_headers, key="tg:1:100")
    second = await create(client, auth_headers, key="tg:1:100")

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(storage.objects) == 1


async def test_storage_failure_does_not_create_product(client, auth_headers, storage):
    storage.fail_next_put = True
    response = await create(client, auth_headers)
    assert response.status_code == 500

    listing = await client.get("/api/v1/products")
    assert listing.json()["items"] == []


async def test_list_is_newest_first_with_cursor(client, auth_headers):
    names = [f"Товар {i}" for i in range(5)]
    for name in names:
        assert (await create(client, auth_headers, name=name)).status_code == 201

    seen: list[str] = []
    cursor = None
    for _ in range(10):
        params = {"cursor": cursor} if cursor else {}
        page = (await client.get("/api/v1/products", params=params)).json()
        seen.extend(item["name"] for item in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break

    assert seen == list(reversed(names))


async def test_list_limit_is_capped(client, auth_headers):
    for i in range(6):
        await create(client, auth_headers, name=f"Товар {i}")

    page = (await client.get("/api/v1/products", params={"limit": 1000})).json()
    assert len(page["items"]) == 5
    assert page["next_cursor"] is not None


async def test_list_rejects_malformed_cursor(client):
    response = await client.get("/api/v1/products", params={"cursor": "%%%garbage"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


async def test_get_product(client, auth_headers):
    created = (await create(client, auth_headers)).json()

    response = await client.get(f"/api/v1/products/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created

    missing = await client.get("/api/v1/products/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
