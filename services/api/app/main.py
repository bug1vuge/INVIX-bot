import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import health, products
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import create_engine, create_sessionmaker
from app.services.errors import ServiceError
from app.storage.s3 import ObjectStorage

logger = logging.getLogger(__name__)


def _error(status_code: int, code: str, message: str, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "unauthorized" if exc.status_code == 401 else "http_error"
        return _error(exc.status_code, code, str(exc.detail), getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"{field}: {first.get('msg')}" if field else "Invalid request"
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error", message)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Internal error")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        storage = ObjectStorage(settings)
        await storage.connect()

        app.state.engine = engine
        app.state.sessionmaker = create_sessionmaker(engine)
        app.state.storage = storage
        logger.info("api started", extra={"environment": settings.environment})
        try:
            yield
        finally:
            await storage.close()
            await engine.dispose()
            logger.info("api stopped")

    is_dev = settings.environment != "production"
    app = FastAPI(
        title="Catalog API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if is_dev else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if is_dev else None,
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(products.router)
    return app
