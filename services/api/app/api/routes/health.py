import asyncio
import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import SessionDep, StorageDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

CHECK_TIMEOUT_SECONDS = 3


@router.get("/live")
async def live() -> dict[str, str]:
    """The process is up and serving requests. Never touches dependencies."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: SessionDep, storage: StorageDep, response: Response) -> dict:
    """The replica can serve traffic: database and object storage respond."""
    checks: dict[str, str] = {}

    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.warning("readiness: database check failed", exc_info=True)
        checks["database"] = "fail"

    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            await storage.ping()
        checks["storage"] = "ok"
    except Exception:
        logger.warning("readiness: storage check failed", exc_info=True)
        checks["storage"] = "fail"

    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "fail", "checks": checks}
