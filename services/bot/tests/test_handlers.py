from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardMarkup

from bot import texts
from bot.services.catalog_api import CatalogApiError, CatalogUnavailableError
from bot.states import ProductForm
from tests.conftest import ADMIN_ID, PHOTO_BYTES, USER_ID, feed


def sent(app) -> list[str]:
    return app.bot.session.sent_texts()


async def state_of(app, user_id: int) -> str | None:
    from aiogram.fsm.storage.base import StorageKey

    key = StorageKey(bot_id=app.bot.id, chat_id=user_id, user_id=user_id)
    return await app.dispatcher.storage.get_state(key)


async def test_start_shows_catalog_button(app, updates):
    await feed(app, updates.message(USER_ID, text="/start"))

    [request] = app.bot.session.requests
    assert isinstance(request, SendMessage)
    assert request.text == texts.GREETING
    assert isinstance(request.reply_markup, InlineKeyboardMarkup)
    button = request.reply_markup.inline_keyboard[0][0]
    assert button.web_app.url == "https://shop.example.com"


async def test_any_message_gets_greeting(app, updates):
    await feed(app, updates.message(USER_ID, text="привет"))
    assert sent(app) == [texts.GREETING]


async def test_regular_user_cannot_create_products(app, updates):
    await feed(app, updates.message(USER_ID, text=texts.CREATE_PRODUCT_BUTTON))
    await feed(app, updates.photo(USER_ID, caption="Чайник"))

    assert app.catalog.calls == []
    assert sent(app) == [texts.GREETING, texts.GREETING]


async def test_admin_sees_create_hint(app, updates):
    await feed(app, updates.message(ADMIN_ID, text="/start"))
    assert sent(app)[0] == texts.GREETING
    assert texts.CREATE_PRODUCT_BUTTON in sent(app)[1]


async def test_admin_creates_product_via_button(app, updates):
    await feed(app, updates.message(ADMIN_ID, text=texts.CREATE_PRODUCT_BUTTON))
    assert await state_of(app, ADMIN_ID) == ProductForm.waiting_for_product.state

    update = updates.photo(ADMIN_ID, caption="  Чайник   стеклянный ")
    await feed(app, update)

    [call] = app.catalog.calls
    assert call["name"] == "Чайник стеклянный"
    assert call["image"] == PHOTO_BYTES
    assert call["created_by"] == ADMIN_ID
    assert call["idempotency_key"] == f"tg:{ADMIN_ID}:{update.message.message_id}"
    assert texts.PRODUCT_CREATED.format(name="Чайник стеклянный") in sent(app)
    assert await state_of(app, ADMIN_ID) is None

    # The largest photo size must be downloaded.
    file_requests = [r for r in app.bot.session.requests if type(r).__name__ == "GetFile"]
    assert file_requests[0].file_id == "large"


async def test_admin_creates_product_in_one_message(app, updates):
    await feed(app, updates.photo(ADMIN_ID, caption="Лампа"))
    assert [c["name"] for c in app.catalog.calls] == ["Лампа"]


async def test_name_is_html_escaped(app, updates):
    await feed(app, updates.photo(ADMIN_ID, caption="<b>Стол</b>"))
    assert texts.PRODUCT_CREATED.format(name="&lt;b&gt;Стол&lt;/b&gt;") in sent(app)


async def test_photo_without_caption_asks_for_name(app, updates):
    await feed(app, updates.photo(ADMIN_ID))

    assert app.catalog.calls == []
    assert sent(app) == [texts.NEED_CAPTION]
    assert await state_of(app, ADMIN_ID) == ProductForm.waiting_for_product.state


async def test_text_while_waiting_reminds_format(app, updates):
    await feed(app, updates.message(ADMIN_ID, text="/create"))
    await feed(app, updates.message(ADMIN_ID, text="Чайник"))
    assert sent(app)[-1] == texts.NEED_PHOTO


async def test_cancel(app, updates):
    await feed(app, updates.message(ADMIN_ID, text="/create"))
    await feed(app, updates.message(ADMIN_ID, text=texts.CANCEL_BUTTON))

    assert sent(app)[-1] == texts.CANCELLED
    assert await state_of(app, ADMIN_ID) is None


async def test_too_long_name(app, updates):
    await feed(app, updates.photo(ADMIN_ID, caption="x" * 300))
    assert app.catalog.calls == []
    assert sent(app) == [texts.NAME_TOO_LONG.format(limit=255)]


async def test_album_is_rejected_once(app, updates):
    await feed(app, updates.photo(ADMIN_ID, caption="A", media_group_id="g1"))
    await feed(app, updates.photo(ADMIN_ID, media_group_id="g1"))

    assert app.catalog.calls == []
    assert sent(app) == [texts.ONLY_ONE_PHOTO]


async def test_api_rejection_is_explained(app, updates):
    app.catalog.error = CatalogApiError(422, "invalid_image", "File is not a valid image")
    await feed(app, updates.photo(ADMIN_ID, caption="Ваза"))

    expected = texts.PRODUCT_REJECTED.format(reason=texts.API_REASONS["invalid_image"])
    assert sent(app) == [expected]


async def test_unexpected_api_error_is_not_leaked(app, updates):
    app.catalog.error = CatalogApiError(401, "unauthorized", "Invalid or missing service token")
    await feed(app, updates.photo(ADMIN_ID, caption="Ваза"))
    assert sent(app) == [texts.PRODUCT_FAILED]


async def test_api_outage_is_reported(app, updates):
    app.catalog.error = CatalogUnavailableError("down")
    await feed(app, updates.photo(ADMIN_ID, caption="Ваза"))
    assert sent(app) == [texts.PRODUCT_FAILED]


async def test_duplicate_update_is_ignored(app, updates):
    update = updates.photo(ADMIN_ID, caption="Кресло")
    await feed(app, update)
    await feed(app, update)

    assert len(app.catalog.calls) == 1
