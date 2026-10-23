import json
import logging
from contextlib import AsyncExitStack
from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)

IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"


class ObjectStorage:
    """Thin wrapper around an S3-compatible bucket (MinIO in our setup).

    One client is opened per process and reused; aiobotocore keeps its own
    connection pool, so opening a client per request would be wasteful.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bucket = settings.s3_bucket
        self._session = aioboto3.Session()
        self._stack = AsyncExitStack()
        self._client: Any = None

    @property
    def bucket(self) -> str:
        return self._bucket

    async def connect(self) -> None:
        self._client = await self._stack.enter_async_context(
            self._session.client(
                "s3",
                endpoint_url=self._settings.s3_endpoint_url,
                aws_access_key_id=self._settings.s3_access_key.get_secret_value(),
                aws_secret_access_key=self._settings.s3_secret_key.get_secret_value(),
                region_name=self._settings.s3_region,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=5,
                    read_timeout=30,
                ),
            )
        )

    async def close(self) -> None:
        await self._stack.aclose()
        self._client = None

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        await self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            CacheControl=IMMUTABLE_CACHE_CONTROL,
        )

    async def delete_object(self, key: str) -> None:
        try:
            await self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError:
            # Best effort: an orphaned object is harmless, a failed request is not.
            logger.warning("failed to delete object", extra={"key": key}, exc_info=True)

    async def ping(self) -> None:
        await self._client.head_bucket(Bucket=self._bucket)

    async def ensure_bucket(self) -> None:
        """Create the bucket and allow anonymous reads of objects (not listing).

        Meant to run once from the bootstrap job, not from every API replica.
        """
        try:
            await self._client.head_bucket(Bucket=self._bucket)
            logger.info("bucket exists", extra={"bucket": self._bucket})
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("404", "NoSuchBucket"):
                raise
            try:
                await self._client.create_bucket(Bucket=self._bucket)
                logger.info("bucket created", extra={"bucket": self._bucket})
            except ClientError as create_exc:
                code = create_exc.response.get("Error", {}).get("Code")
                if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                    raise

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadObjects",
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self._bucket}/*"],
                }
            ],
        }
        await self._client.put_bucket_policy(Bucket=self._bucket, Policy=json.dumps(policy))
