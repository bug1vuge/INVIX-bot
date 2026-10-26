import unicodedata

from app.services.errors import InvalidProductNameError

NAME_MAX_LENGTH = 255


def normalize_name(raw: str) -> str:
    """Collapse whitespace and reject names that are empty or unprintable.

    Control characters (NUL in particular, which PostgreSQL cannot store in a
    text column) are rejected; invisible format characters such as zero-width
    spaces are dropped so that a name cannot look empty in the catalog.
    """
    if any(unicodedata.category(char) == "Cc" and not char.isspace() for char in raw):
        raise InvalidProductNameError("Product name must not contain control characters")

    visible = "".join(char for char in raw if unicodedata.category(char) != "Cf")
    name = " ".join(visible.split())
    if not name:
        raise InvalidProductNameError("Product name must not be empty")
    if len(name) > NAME_MAX_LENGTH:
        raise InvalidProductNameError(f"Product name must not exceed {NAME_MAX_LENGTH} characters")
    return name
