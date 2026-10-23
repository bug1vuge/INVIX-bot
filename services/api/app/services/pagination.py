import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.services.errors import InvalidCursorError


@dataclass(frozen=True, slots=True)
class Cursor:
    """Keyset position: the last seen (created_at, id) pair.

    Keyset pagination keeps pages stable while new products are being added
    and does not degrade on deep pages the way OFFSET does.
    """

    created_at: datetime
    id: uuid.UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}|{self.id}".encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str) -> "Cursor":
        try:
            padded = value + "=" * (-len(value) % 4)
            raw = base64.urlsafe_b64decode(padded.encode()).decode()
            created_at, product_id = raw.split("|", 1)
            return cls(created_at=datetime.fromisoformat(created_at), id=uuid.UUID(product_id))
        except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
            raise InvalidCursorError("Malformed cursor") from exc
