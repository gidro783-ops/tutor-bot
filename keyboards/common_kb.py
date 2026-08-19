from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=f"{prefix}:yes")
    builder.button(text="❌ Нет", callback_data=f"{prefix}:no")
    builder.adjust(2)
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel")
    return builder.as_markup()


def pagination_keyboard(prefix: str, page: int,
                        total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="◀️", callback_data=f"{prefix}:page:{page - 1}")
    builder.button(text=f"{page + 1}/{total_pages}", callback_data="noop")
    if page < total_pages - 1:
        builder.button(text="▶️", callback_data=f"{prefix}:page:{page + 1}")
    builder.adjust(3)
    return builder.as_markup()