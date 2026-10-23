from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.services.products import ProductService
from app.storage.s3 import ObjectStorage

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_storage(request: Request) -> ObjectStorage:
    return request.app.state.storage


StorageDep = Annotated[ObjectStorage, Depends(get_storage)]


def get_product_service(
    session: SessionDep, storage: StorageDep, settings: SettingsDep
) -> ProductService:
    return ProductService(session, storage, settings)


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
