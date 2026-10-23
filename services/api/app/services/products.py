import logging
import uuid

from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.models import Product
from app.schemas.product import ProductOut, ProductPage
from app.services.errors import ImageTooLargeError
from app.services.images import inspect_image
from app.services.pagination import Cursor
from app.storage.s3 import ObjectStorage

logger = logging.getLogger(__name__)


class ProductService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage, settings: Settings) -> None:
        self._session = session
        self._storage = storage
        self._settings = settings

    def to_out(self, product: Product) -> ProductOut:
        base = self._settings.media_public_url.rstrip("/")
        return ProductOut(
            id=product.id,
            name=product.name,
            image_url=f"{base}/{product.image_key}",
            image_width=product.image_width,
            image_height=product.image_height,
            created_at=product.created_at,
        )

    async def list_page(self, limit: int, cursor: str | None) -> ProductPage:
        stmt = select(Product).order_by(Product.created_at.desc(), Product.id.desc())
        if cursor:
            position = Cursor.decode(cursor)
            stmt = stmt.where(
                tuple_(Product.created_at, Product.id) < tuple_(position.created_at, position.id)
            )

        # Fetch one extra row to know whether another page exists.
        rows = list((await self._session.scalars(stmt.limit(limit + 1))).all())
        has_more = len(rows) > limit
        rows = rows[:limit]

        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = Cursor(created_at=last.created_at, id=last.id).encode()

        return ProductPage(items=[self.to_out(p) for p in rows], next_cursor=next_cursor)

    async def get_by_idempotency_key(self, key: str) -> Product | None:
        return await self._session.scalar(select(Product).where(Product.idempotency_key == key))

    async def create(
        self,
        *,
        name: str,
        image: bytes,
        idempotency_key: str | None = None,
        created_by: int | None = None,
    ) -> tuple[Product, bool]:
        """Store the image and create the product.

        Returns the product and a flag telling whether it was created by this
        call (False means an earlier request with the same key already did it).
        """
        if idempotency_key:
            existing = await self.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing, False

        if len(image) > self._settings.max_image_size_bytes:
            raise ImageTooLargeError(f"Image must not exceed {self._settings.max_image_size_mb} MB")

        info = await run_in_threadpool(inspect_image, image, self._settings.max_image_pixels)

        product_id = uuid.uuid4()
        image_key = f"products/{product_id.hex}.{info.extension}"

        # Upload first: a row pointing to a missing object would be a broken
        # card in the catalog, while an orphaned object is merely garbage.
        await self._storage.put_object(image_key, image, info.content_type)

        product = Product(
            id=product_id,
            name=name,
            image_key=image_key,
            image_content_type=info.content_type,
            image_width=info.width,
            image_height=info.height,
            idempotency_key=idempotency_key,
            created_by=created_by,
        )
        self._session.add(product)

        try:
            await self._session.commit()
        except IntegrityError:
            # Two replicas raced on the same idempotency key; the other one won.
            await self._session.rollback()
            await self._storage.delete_object(image_key)
            if idempotency_key:
                existing = await self.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing, False
            raise
        except BaseException:
            await self._session.rollback()
            await self._storage.delete_object(image_key)
            raise

        await self._session.refresh(product)
        logger.info(
            "product created",
            extra={"product_id": str(product.id), "created_by": created_by},
        )
        return product, True
