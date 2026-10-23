import asyncio
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = frozenset({502, 503, 504})


class CatalogApiError(Exception):
    """The API rejected the request; retrying will not help."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(f"{status_code} {code}: {message}")
        self.status_code = status_code
        self.code = code
        self.message = message


class CatalogUnavailableError(Exception):
    """The API could not be reached or kept failing after retries."""


@dataclass(frozen=True, slots=True)
class CreatedProduct:
    id: str
    name: str
    image_url: str


class CatalogClient:
    def __init__(
        self,
        base_url: str,
        service_token: str,
        timeout: float = 15.0,
        attempts: int = 3,
        backoff: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._attempts = attempts
        self._backoff = backoff
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=5.0),
            headers={"Authorization": f"Bearer {service_token}"},
            transport=transport,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def create_product(
        self,
        *,
        name: str,
        image: bytes,
        filename: str,
        idempotency_key: str,
        created_by: int | None = None,
    ) -> CreatedProduct:
        """Create a product, retrying transient failures.

        Retries are safe: the API deduplicates requests by Idempotency-Key.
        """
        data: dict[str, str] = {"name": name}
        if created_by is not None:
            data["created_by"] = str(created_by)

        last_error: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                response = await self._http.post(
                    "/api/v1/products",
                    data=data,
                    files={"image": (filename, image, "application/octet-stream")},
                    headers={"Idempotency-Key": idempotency_key},
                )
            except httpx.TransportError as exc:
                last_error = exc
                logger.warning(
                    "catalog api request failed", extra={"attempt": attempt, "error": repr(exc)}
                )
            else:
                if response.status_code < 400:
                    body = response.json()
                    return CreatedProduct(
                        id=body["id"], name=body["name"], image_url=body["image_url"]
                    )
                if response.status_code not in RETRYABLE_STATUSES and response.status_code < 500:
                    raise _to_api_error(response)
                last_error = _to_api_error(response)
                logger.warning(
                    "catalog api returned an error",
                    extra={"attempt": attempt, "status": response.status_code},
                )

            if attempt < self._attempts:
                await asyncio.sleep(self._backoff * 2 ** (attempt - 1))

        raise CatalogUnavailableError("catalog api is unavailable") from last_error


def _to_api_error(response: httpx.Response) -> CatalogApiError:
    try:
        error = response.json()["error"]
        return CatalogApiError(response.status_code, error["code"], error["message"])
    except (ValueError, KeyError, TypeError):
        return CatalogApiError(response.status_code, "http_error", response.text[:200])
