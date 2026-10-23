async def test_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "storage": "ok"}


async def test_ready_reports_storage_failure(client, storage):
    async def broken_ping() -> None:
        raise ConnectionError("no route to host")

    storage.ping = broken_ping
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["storage"] == "fail"


async def test_request_id_is_propagated(client):
    response = await client.get("/health/live", headers={"X-Request-ID": "abc123"})
    assert response.headers["x-request-id"] == "abc123"
