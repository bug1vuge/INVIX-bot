from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.services.errors import InvalidImageError

# Pillow format name -> (content type, file extension)
SUPPORTED_FORMATS: dict[str, tuple[str, str]] = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


@dataclass(frozen=True, slots=True)
class ImageInfo:
    content_type: str
    extension: str
    width: int
    height: int


def inspect_image(data: bytes, max_pixels: int) -> ImageInfo:
    """Check that the payload is a real image of a supported format.

    The content type sent by the client is not trusted: the format is detected
    from the bytes. CPU-bound, call it from a worker thread.
    """
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = img.format
            width, height = img.size
            if width * height > max_pixels:
                raise InvalidImageError("Image resolution is too large")
            img.verify()
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("File is not a valid image") from exc

    if fmt not in SUPPORTED_FORMATS:
        raise InvalidImageError("Only JPEG, PNG and WebP images are supported")

    content_type, extension = SUPPORTED_FORMATS[fmt]
    return ImageInfo(content_type=content_type, extension=extension, width=width, height=height)
