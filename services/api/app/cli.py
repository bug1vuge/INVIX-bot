"""Operational commands that must run once per deploy, not once per replica.

python -m app.cli bootstrap   # apply migrations and prepare the bucket
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.storage.s3 import ObjectStorage

logger = logging.getLogger("app.cli")

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def migrate() -> None:
    logger.info("applying migrations")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


async def prepare_storage(attempts: int = 10, delay: float = 3.0) -> None:
    storage = ObjectStorage(get_settings())
    await storage.connect()
    try:
        for attempt in range(1, attempts + 1):
            try:
                await storage.ensure_bucket()
                return
            except Exception:
                if attempt == attempts:
                    raise
                logger.warning("storage is not ready yet, retrying", extra={"attempt": attempt})
                await asyncio.sleep(delay)
    finally:
        await storage.close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="apply migrations and prepare object storage")
    sub.add_parser("migrate", help="apply database migrations only")
    args = parser.parse_args()

    setup_logging(get_settings().log_level)

    if args.command in ("bootstrap", "migrate"):
        migrate()
    if args.command == "bootstrap":
        asyncio.run(prepare_storage())

    logger.info("done", extra={"command": args.command})
    return 0


if __name__ == "__main__":
    sys.exit(main())
