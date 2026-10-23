import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))

    image_key: Mapped[str] = mapped_column(String(512))
    image_content_type: Mapped[str] = mapped_column(String(64))
    image_width: Mapped[int] = mapped_column(Integer)
    image_height: Mapped[int] = mapped_column(Integer)

    # Set by clients that may retry the same request (the bot passes the
    # Telegram chat/message pair), so a retry never creates a duplicate.
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger)

    # Python-side default keeps microsecond precision on every backend and
    # makes the keyset order deterministic; the server default covers raw SQL.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    __table_args__ = (Index("ix_products_created_at_id", created_at.desc(), id.desc()),)

    def __repr__(self) -> str:
        return f"Product(id={self.id!s}, name={self.name!r})"
