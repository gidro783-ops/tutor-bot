# -*- coding: utf-8 -*-
"""Клавиатуры витрины подписок (Free / PRO / White Label)."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from services.subscription import PLANS, Plan


def plans_kb(show_trial: bool = False) -> InlineKeyboardMarkup:
    """Витрина тарифов: триал (если доступен) + покупка PRO/White Label."""
    builder = InlineKeyboardBuilder()
    if show_trial:
        builder.button(
            text=f"🎁 Попробовать PRO бесплатно (7 дней)", callback_data="start_trial"
        )
    pro = PLANS[Plan.PRO]
    wl = PLANS[Plan.WHITE_LABEL]
    builder.button(
        text=f"💳 PRO — {pro.price_rub} ₽/мес", callback_data=f"buy_plan:{Plan.PRO.value}"
    )
    if config.PRO_PRICE_STARS > 0:
        builder.button(
            text=f"⭐ PRO — {config.PRO_PRICE_STARS} звёзд",
            callback_data=f"buy_plan_stars:{Plan.PRO.value}",
        )
    builder.button(
        text=f"👑 White Label — {wl.price_rub} ₽/мес",
        callback_data=f"buy_plan:{Plan.WHITE_LABEL.value}",
    )
    builder.adjust(1)
    return builder.as_markup()


def subscription_menu_kb(sub) -> InlineKeyboardMarkup:
    """Меню после оплаты/просмотра подписки: вернуться к тарифам."""
    builder = InlineKeyboardBuilder()
    if sub.effective_info.code != Plan.WHITE_LABEL:
        builder.button(text="💳 Тарифы и оплата", callback_data="open_plans")
    builder.button(text="◀️ Закрыть", callback_data="admin:back")
    builder.adjust(1)
    return builder.as_markup()


def cancel_flow_kb() -> InlineKeyboardMarkup:
    """Универсальная «❌ Отмена» для шагов ввода текста."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_flow")
    return builder.as_markup()
