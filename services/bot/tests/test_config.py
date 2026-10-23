import pytest
from pydantic import ValidationError

from bot.config import Settings

BASE = {
    "bot_token": "1:x",
    "service_token": "s",
    "webapp_url": "https://shop.example.com",
}


def test_admin_ids_are_parsed_from_comma_list(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "111, 222;333")
    settings = Settings(**BASE, bot_mode="polling")
    assert settings.admin_ids == frozenset({111, 222, 333})
    assert settings.is_admin(222)
    assert not settings.is_admin(None)


def test_webhook_mode_requires_https_url():
    with pytest.raises(ValidationError):
        Settings(**BASE, bot_mode="webhook", webhook_base_url="http://x", webhook_secret="s" * 32)


def test_webhook_mode_requires_strong_secret():
    with pytest.raises(ValidationError):
        Settings(**BASE, bot_mode="webhook", webhook_base_url="https://x", webhook_secret="short")


def test_webhook_url():
    settings = Settings(
        **BASE,
        bot_mode="webhook",
        webhook_base_url="https://shop.example.com/",
        webhook_secret="s" * 32,
    )
    assert settings.webhook_url == "https://shop.example.com/bot/webhook"
