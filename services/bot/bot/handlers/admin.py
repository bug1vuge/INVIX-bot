import logging
from io import BytesIO

from aiogram import Bot, F, Router, html
from aiogram.enums import ChatAction
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from redis.asyncio import Redis

from bot import texts
from bot.config import Settings
from bot.filters import IsAdmin
from bot.keyboards import admin_menu_keyboard, cancel_keyboard, catalog_keyboard
from bot.services.catalog_api import CatalogApiError, CatalogClient, CatalogUnavailableError
from bot.states import ProductForm

logger = logging.getLogger(__name__)

NAME_MAX_LENGTH = 255
IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

image_document = F.document.mime_type.in_(IMAGE_MIME_TYPES)


async def start_creation(message: Message, state: FSMContext) -> None:
    await state.set_state(ProductForm.waiting_for_product)
    await message.answer(
        texts.ASK_PRODUCT.format(cancel=texts.CANCEL_BUTTON),
        reply_markup=cancel_keyboard(),
    )


async def cancel_creation(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL, reply_markup=admin_menu_keyboard())
        return
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=admin_menu_keyboard())


async def reject_album(message: Message, redis: Redis) -> None:
    # Every photo of an album arrives as a separate update; answer only once.
    key = f"bot:album:{message.chat.id}:{message.media_group_id}"
    if await redis.set(key, "1", nx=True, ex=60):
        await message.answer(texts.ONLY_ONE_PHOTO)


async def create_product(
    message: Message,
    state: FSMContext,
    bot: Bot,
    settings: Settings,
    catalog: CatalogClient,
) -> None:
    name = " ".join((message.caption or "").split())
    if not name:
        await state.set_state(ProductForm.waiting_for_product)
        await message.answer(texts.NEED_CAPTION, reply_markup=cancel_keyboard())
        return
    if len(name) > NAME_MAX_LENGTH:
        await message.answer(texts.NAME_TOO_LONG.format(limit=NAME_MAX_LENGTH))
        return

    if message.photo:
        file = message.photo[-1]  # the largest available size
        filename = f"{file.file_unique_id}.jpg"
    else:
        file = message.document
        filename = file.file_name or f"{file.file_unique_id}"

    if file.file_size and file.file_size > settings.max_photo_size_bytes:
        await message.answer(texts.PHOTO_TOO_LARGE.format(limit=settings.max_photo_size_mb))
        return

    await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)

    buffer = BytesIO()
    await bot.download(file, destination=buffer)

    try:
        product = await catalog.create_product(
            name=name,
            image=buffer.getvalue(),
            filename=filename,
            # A redelivered update maps to the same key, so no duplicate product.
            idempotency_key=f"tg:{message.chat.id}:{message.message_id}",
            created_by=message.from_user.id if message.from_user else None,
        )
    except CatalogApiError as exc:
        reason = texts.API_REASONS.get(exc.code)
        if reason is None:
            # Not the admin's fault (bad token, unexpected response): alert, don't explain.
            logger.error("catalog api error", extra={"code": exc.code, "status": exc.status_code})
            await message.answer(texts.PRODUCT_FAILED)
            return
        logger.info("product rejected by api", extra={"code": exc.code})
        await message.answer(texts.PRODUCT_REJECTED.format(reason=html.quote(reason)))
        return
    except CatalogUnavailableError:
        logger.exception("catalog api is unavailable")
        await message.answer(texts.PRODUCT_FAILED)
        return

    await state.clear()
    await message.answer(
        texts.PRODUCT_CREATED.format(name=html.quote(product.name)),
        reply_markup=admin_menu_keyboard(),
    )
    await message.answer(texts.GREETING, reply_markup=catalog_keyboard(settings.webapp_url))


async def reject_unsupported_file(message: Message) -> None:
    await message.answer(texts.UNSUPPORTED_FILE)


async def remind_format(message: Message) -> None:
    await message.answer(texts.NEED_PHOTO, reply_markup=cancel_keyboard())


def create_router() -> Router:
    router = Router(name="admin")
    router.message.filter(F.chat.type == "private", IsAdmin())

    router.message.register(start_creation, Command("create"))
    router.message.register(start_creation, F.text == texts.CREATE_PRODUCT_BUTTON)
    router.message.register(cancel_creation, Command("cancel"))
    router.message.register(cancel_creation, F.text == texts.CANCEL_BUTTON)
    router.message.register(reject_album, F.media_group_id, F.photo | image_document)
    router.message.register(create_product, F.photo | image_document)
    router.message.register(
        reject_unsupported_file, StateFilter(ProductForm.waiting_for_product), F.document
    )
    router.message.register(remind_format, StateFilter(ProductForm.waiting_for_product))
    return router
