import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    image_url: str
    image_width: int
    image_height: int
    created_at: datetime


class ProductPage(BaseModel):
    items: list[ProductOut]
    next_cursor: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
