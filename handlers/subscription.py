"""Витрина тарифов, пробный период, защищённая оплата, white-label."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from config import config
from keyboards.subscription_kb import (
    cancel_flow_kb,
    plans_kb,
    subscription_menu_kb,
)
from services import subscription as sub_service
from services.subscription import PLANS, Plan, TRIAL_DAYS
from utils.helpers import is_cancel

logger = logging.getLogger(__name__)
router = Router(name="subscription")
CURRENCY = "RUB"


class BrandStates(StatesGroup):
    name = State()
    about = State()


def _caption(sub) -> str:
    info = sub.effective_info
    lines = [f"<b>Ваш тариф:</b> {info.title}" + (" (пробный)" if sub.is_trial else "")]
    if sub.days_left is not None:
        lines.append(f"Осталось дней: <b>{sub.days_left}</b>")
    limit = "безлимит" if info.max_students is None else str(info.max_students)
    lines.append(f"Лимит учеников: <b>{limit}</b>")
    return "\n".join(lines)


@router.message(Command("subscription"))
@router.message(F.text == "💎 Подписка")
async def show_subscription(message: Message):
    sub = await sub_service.get_subscription(message.from_user.id)
    show_trial = (not sub.trial_used) and sub.plan == Plan.FREE
    await message.answer(f"{_caption(sub)}\n\nВыберите тариф:",
                         reply_markup=plans_kb(show_trial=show_trial))


@router.callback_query(F.data == "open_plans")
async def open_plans(call: CallbackQuery):
    sub = await sub_service.get_subscription(call.from_user.id)
    show_trial = (not sub.trial_used) and sub.plan == Plan.FREE
    await call.message.answer("Выберите тариф:", reply_markup=plans_kb(show_trial=show_trial))
    await call.answer()


@router.callback_query(F.data == "start_trial")
async def on_start_trial(call: CallbackQuery):
    sub = await sub_service.start_trial(call.from_user.id)
    if sub is None:
        await call.message.answer("Пробный период уже был использован.")
    else:
        await call.message.answer(
            f"🎁 Пробный период PRO на {TRIAL_DAYS} дней активирован!\n"
            f"Действует до <b>{sub.expires_at:%d.%m.%Y}</b>. Все функции открыты."
        )
    await call.answer()


@router.callback_query(F.data.startswith("buy_plan:"))
async def buy_plan(call: CallbackQuery):
    plan = Plan(call.data.split(":", 1)[1])
    info = PLANS[plan]
    if not config.PAYMENT_PROVIDER_TOKEN:
        await call.message.answer(
            f"Оплата тарифа {info.title} — {info.price_rub} руб/мес.\n"
            "Платёжный провайдер не настроен (PAYMENT_PROVIDER_TOKEN в .env)."
        )
        await call.answer()
        return
    await call.message.answer_invoice(
        title=f"Подписка {info.title}",
        description=f"Доступ к тарифу {info.title} на 1 месяц.",
        payload=f"sub:{plan.value}",
        provider_token=config.PAYMENT_PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=[LabeledPrice(label=f"{info.title} — 1 мес", amount=info.price_rub * 100)],
        start_parameter="subscription",
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    """Валидация заказа ДО списания денег."""
    payload = query.invoice_payload or ""
    if not payload.startswith("sub:"):
        await query.answer(ok=False, error_message="Некорректный идентификатор заказа.")
        logger.warning("Bad payload in pre_checkout: %r", payload)
        return
    plan_code = payload.split(":", 1)[1]
    if plan_code not in {p.value for p in Plan}:
        await query.answer(ok=False, error_message="Выбран неизвестный тариф.")
        logger.warning("Unknown plan in pre_checkout: %r", plan_code)
        return
    if plan_code == Plan.FREE.value:
        await query.answer(ok=False, error_message="Бесплатный тариф не требует оплаты.")
        return
    expected = PLANS[Plan(plan_code)].price_rub * 100
    if query.total_amount != expected:
        await query.answer(ok=False, error_message="Сумма платежа не совпадает с тарифом.")
        logger.warning("Amount mismatch: got %s, expected %s", query.total_amount, expected)
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_paid(message: Message):
    payload = message.successful_payment.invoice_payload
    if not payload.startswith("sub:"):
        return
    plan = Plan(payload.split(":", 1)[1])
    sub = await sub_service.activate(message.from_user.id, plan, months=1)
    await message.answer(
        f"✅ Оплата принята! Тариф {PLANS[plan].title} активен до "
        f"<b>{sub.expires_at:%d.%m.%Y}</b>",
        reply_markup=subscription_menu_kb(sub),
    )
    if plan == Plan.WHITE_LABEL:
        await message.answer("👑 White Label активен. Настройте бренд командой /brand.")


@router.message(Command("brand"))
async def brand_start(message: Message, state: FSMContext):
    if not await sub_service.feature_enabled(message.from_user.id, "white_label"):
        await message.answer("Брендинг доступен только на тарифе White Label.")
        return
    await state.set_state(BrandStates.name)
    await message.answer(
        "Введите название бренда (имя, которое увидят ученики):",
        reply_markup=cancel_flow_kb(),
    )


@router.message(BrandStates.name)
async def brand_name(message: Message, state: FSMContext):
    if is_cancel(message.text):
        await state.clear()
        await message.answer("❌ Настройка бренда отменена.")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(BrandStates.about)
    await message.answer(
        "Короткое описание (или '-' чтобы пропустить):",
        reply_markup=cancel_flow_kb(),
    )


@router.message(BrandStates.about)
async def brand_about(message: Message, state: FSMContext):
    if is_cancel(message.text):
        await state.clear()
        await message.answer("❌ Настройка бренда отменена.")
        return
    data = await state.get_data()
    about = None if message.text.strip() == "-" else message.text.strip()
    await sub_service.set_brand(message.from_user.id, data["name"], about)
    await state.clear()
    await message.answer(f"✅ Бренд сохранён: <b>{data['name']}</b>")
