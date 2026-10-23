from aiogram.fsm.state import State, StatesGroup


class ProductForm(StatesGroup):
    waiting_for_product = State()
