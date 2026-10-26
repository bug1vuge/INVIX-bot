import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status

from app.api.deps import ProductServiceDep, SessionDep, SettingsDep
from app.core.security import require_service_token
from app.models import Product
from app.schemas.product import ErrorResponse, ProductOut, ProductPage
from app.services.errors import ImageTooLargeError, ProductNotFoundError
from app.services.names import normalize_name

router = APIRouter(prefix="/api/v1/products", tags=["products"])

# created_by is stored as BIGINT (Telegram user ids fit into it).
BIGINT_MAX = 2**63 - 1


@router.get("", response_model=ProductPage)
async def list_products(
    service: ProductServiceDep,
    settings: SettingsDep,
    response: Response,
    limit: Annotated[int | None, Query(ge=1)] = None,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> ProductPage:
    page_size = min(limit or settings.page_size_default, settings.page_size_max)
    response.headers["Cache-Control"] = "no-cache"
    return await service.list_page(limit=page_size, cursor=cursor)


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    responses={404: {"model": ErrorResponse}},
)
async def get_product(
    product_id: uuid.UUID, session: SessionDep, service: ProductServiceDep
) -> ProductOut:
    product = await session.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError("Product not found")
    return service.to_out(product)


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_token)],
    responses={
        200: {"model": ProductOut, "description": "Replay of an already processed request"},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def create_product(
    service: ProductServiceDep,
    settings: SettingsDep,
    response: Response,
    name: Annotated[str, Form()],
    image: Annotated[UploadFile, File()],
    created_by: Annotated[int | None, Form(ge=1, le=BIGINT_MAX)] = None,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
) -> ProductOut:
    clean_name = normalize_name(name)

    # Read one byte past the limit to detect oversized uploads without
    # buffering arbitrarily large bodies in memory.
    data = await image.read(settings.max_image_size_bytes + 1)
    if len(data) > settings.max_image_size_bytes:
        raise ImageTooLargeError(f"Image must not exceed {settings.max_image_size_mb} MB")

    product, created = await service.create(
        name=clean_name,
        image=data,
        idempotency_key=idempotency_key,
        created_by=created_by,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.to_out(product)
