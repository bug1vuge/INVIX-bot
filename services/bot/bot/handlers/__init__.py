from aiogram import Router

from bot.handlers import admin, common, errors


def build_router() -> Router:
    root = Router(name="root")
    # Order matters: admin handlers must see messages before the catch-all.
    root.include_routers(
        errors.create_router(),
        admin.create_router(),
        common.create_router(),
    )
    return root
