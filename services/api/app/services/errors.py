class ServiceError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidImageError(ServiceError):
    status_code = 422
    code = "invalid_image"


class ImageTooLargeError(ServiceError):
    status_code = 413
    code = "image_too_large"


class InvalidProductNameError(ServiceError):
    status_code = 422
    code = "invalid_name"


class ProductNotFoundError(ServiceError):
    status_code = 404
    code = "not_found"


class InvalidCursorError(ServiceError):
    status_code = 400
    code = "invalid_cursor"
