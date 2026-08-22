# -*- coding: utf-8 -*-
"""Админка: настройка ИИ-ассистента.

«Обучение» ИИ = анкета репетитора (имя, предметы и цены, формат).
Она попадает в системный промпт, и ИИ отвечает ученикам от лица
репетитора, не выдумывая ничего сверх анкеты и FAQ.
"""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from database import db
from keyboards.subscription_kb import cancel_flow_kb
from services import ai_assistant, subscription as sub_service

from .core import check_admin

logger = logging.getLogger(__name__)
router = Router()


class AiSetup(StatesGroup):
    field = State()
    exclude = State()


# какое поле анкеты редактируем: callback → (ключ в bot_settings, подпись)
FIELDS = {
    "admin:ai:name": (
        ai_assistant.KB_NAME,
        "👤 Введите имя репетитора, как должны обращаться ученики "
        "(например: «Мария, репетитор по математике»):",
    ),
    "admin:ai:subjects": (
        ai_assistant.KB_SUBJECTS,
        "📚 Перечислите предметы и цены — по строке на предмет.\n"
        "Пример:\nМатематика — 1200 ₽/час\nОГЭ-подготовка — 1500 ₽/час",
    ),
    "admin:ai:about": (
        ai_assistant.KB_ABOUT,
        "📋 Опишите опыт, формат занятий и условия.\n"
        "Пример: 8 лет опыта, онлайн в Zoom, пробное занятие бесплатно, "
        "отмена не позднее чем за 12 часов.",
    ),
}


def _ai_menu_kb(enabled: bool, dm_enabled: bool) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Имя", callback_data="admin:ai:name")
    builder.button(text="📚 Предметы и цены", callback_data="admin:ai:subjects")
    builder.button(text="📋 Опыт и формат", callback_data="admin:ai:about")
    builder.button(
        text=("🔁 Включить ассистента" if not enabled else "⏸ Выключить ассистента"),
        callback_data="admin:ai:toggle",
    )
    builder.button(
        text=(
            "✉️ Автоответы в ЛС: выкл"
            if not dm_enabled
            else "✉️ Автоответы в ЛС: ВКЛ"
        ),
        callback_data="admin:ai:dm_toggle",
    )
    builder.button(text="🚫 Исключения (не отвечать)", callback_data="admin:ai:skip")
    builder.button(text="🧪 Проверить ИИ", callback_data="admin:ai:test")
    builder.button(text="◀️ В меню", callback_data="admin:back")
    builder.adjust(2, 1, 1, 1, 1)
    return builder


@router.callback_query(F.data == "admin:ai")
async def ai_settings(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.clear()
    await _show_ai_settings(callback)


async def _show_ai_settings(target):
    """Показать меню настроек ИИ. target — CallbackQuery или Message."""
    from services import ai_replies
    from services.userbot import userbot as ub

    enabled = await db.get_setting(ai_assistant.KB_ENABLED, "0") == "1"
    dm_enabled = await db.get_setting(ai_replies.DM_ENABLED_KEY, "0") == "1"
    key_ok = bool(config.AI_API_KEY)
    name = await db.get_setting(ai_assistant.KB_NAME, "")
    subjects = await db.get_setting(ai_assistant.KB_SUBJECTS, "")
    about = await db.get_setting(ai_assistant.KB_ABOUT, "")
    skip_count = len(await ai_replies.get_skip_list())

    status = "🟢 включён" if enabled and key_ok else "🔴 выключен"
    if not key_ok:
        status += " (нет AI_API_KEY в .env)"
    elif not enabled:
        status += " (выключен кнопкой)"

    dm_status = "🔴 выкл"
    if dm_enabled and key_ok:
        dm_status = "🟢 ВКЛ" if ub.is_connected else "🟡 вкл, но userbot не подключён"
    dm_hint = ""
    if dm_enabled and not ub.is_connected:
        dm_hint = "\n⚠️ Для ответов в ЛС подключите userbot (Рассылки → Userbot)."
    if not config.AI_API_KEY:
        dm_hint = "\n⚠️ Добавьте AI_API_KEY в .env."

    quota_note = "безлимит (PRO)"
    owner = config.ADMIN_IDS[0] if config.ADMIN_IDS else None
    if owner is not None:
        left = await sub_service.ai_answers_left_today(owner)
        if left is not None:
            quota_note = f"осталось сегодня: {left} из 10 (Free)"

    text = (
        f"🤖 <b>ИИ-ассистент</b>\n\n"
        f"В боте (кнопка «🤖 Спросить»): {status}\n"
        f"В личных сообщениях аккаунта: {dm_status}\n"
        f"Модель: <code>{config.AI_MODEL}</code>\n"
        f"Ответов ИИ сегодня: {quota_note}\n"
        f"🚫 Исключений (ЛС): {skip_count}\n\n"
        f"👤 Имя: {name or '— не заполнено'}\n"
        f"📚 Предметы: {'✅ заполнено' if subjects else '— не заполнено'}\n"
        f"📋 Опыт: {'✅ заполнено' if about else '— не заполнено'}\n\n"
        f"ИИ отвечает только по этой анкете и вашему FAQ — ничего не "
        f"выдумывает. В ЛС отвечает всем, кроме списка исключений; если "
        f"вы ответили человеку сами — ИИ молчит у него 24 часа.{dm_hint}"
    )
    markup = _ai_menu_kb(enabled, dm_enabled).as_markup()
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("admin:ai:toggle"))
async def ai_toggle(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    if not config.AI_API_KEY:
        await callback.answer(
            "Сначала добавьте AI_API_KEY в .env и перезапустите бота",
            show_alert=True,
        )
        return
    current = await db.get_setting(ai_assistant.KB_ENABLED, "0") == "1"
    await db.set_setting(ai_assistant.KB_ENABLED, "0" if current else "1")
    await callback.answer("Сохранено")
    await _show_ai_settings(callback)


@router.callback_query(F.data.in_(set(FIELDS)))
async def ai_edit_field(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    key, prompt = FIELDS[callback.data]
    await state.update_data(ai_field=key)
    await state.set_state(AiSetup.field)
    await callback.message.edit_text(prompt, reply_markup=cancel_flow_kb())


@router.message(AiSetup.field)
async def ai_save_field(message: Message, state: FSMContext):
    from utils.helpers import is_cancel

    if is_cancel(message.text):
        await state.clear()
        await message.answer("❌ Редактирование отменено.")
        return
    data = await state.get_data()
    key = data.get("ai_field")
    if not key:
        await state.clear()
        return
    value = message.text.strip()
    if not value or len(value) > 3000:
        await message.answer("❌ Текст от 1 до 3000 символов. Попробуйте ещё раз:")
        return
    await db.set_setting(key, value)
    # первая заполненная анкета автоматически включает ассистента
    if await db.get_setting(ai_assistant.KB_ENABLED, "0") != "1" and config.AI_API_KEY:
        await db.set_setting(ai_assistant.KB_ENABLED, "1")
    await state.clear()
    await message.answer("✅ Сохранено. ИИ будет использовать это в ответах.")
    await _show_ai_settings(message)


# =================== АВТООТВЕТЫ В ЛС + ИСКЛЮЧЕНИЯ ===================
@router.callback_query(F.data == "admin:ai:dm_toggle")
async def ai_dm_toggle(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    from services import ai_replies
    from services.userbot import userbot as ub

    if not config.AI_API_KEY:
        await callback.answer("Сначала добавьте AI_API_KEY в .env", show_alert=True)
        return
    current = await db.get_setting(ai_replies.DM_ENABLED_KEY, "0") == "1"
    if not current and not ub.is_connected:
        await callback.answer(
            "Сначала подключите userbot (Рассылки → Userbot), "
            "чтобы ИИ мог читать ЛС аккаунта",
            show_alert=True,
        )
        return
    await db.set_setting(ai_replies.DM_ENABLED_KEY, "0" if current else "1")
    await callback.answer("Сохранено")
    await _show_ai_settings(callback)


@router.callback_query(F.data == "admin:ai:skip")
async def ai_skip_list(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.clear()
    await _show_skip_list(callback)


async def _show_skip_list(callback: CallbackQuery):
    from services import ai_replies

    items = await ai_replies.get_skip_list()
    builder = InlineKeyboardBuilder()
    text = "🚫 <b>Кому ИИ не отвечает в ЛС</b>\n\n"
    if not items:
        text += "Список пуст — ИИ отвечает всем, кто напишет в ЛС."
    for i, item in enumerate(items, start=1):
        uname = item.get("username") or "—"
        uid = item.get("id")
        text += f"{i}. @{escape(uname)}" + (f" (ID: <code>{uid}</code>)" if uid else "") + "\n"
        builder.button(text=f"❌ Убрать @{uname[:20]}", callback_data=f"admin:ai:skip:del:{i-1}")
    builder.button(text="➕ Добавить @username", callback_data="admin:ai:skip:add")
    builder.button(text="◀️ Назад", callback_data="admin:ai")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


def escape(t: str) -> str:
    from utils.helpers import escape_html
    return escape_html(t)


@router.callback_query(F.data.startswith("admin:ai:skip:del:"))
async def ai_skip_del(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    from services import ai_replies

    index = int(callback.data.rsplit(":", 1)[-1])
    await ai_replies.remove_skip(index)
    await callback.answer("Убран")
    await _show_skip_list(callback)


@router.callback_query(F.data == "admin:ai:skip:add")
async def ai_skip_add(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(AiSetup.exclude)
    await callback.message.edit_text(
        "🚫 Введите @username, кому ИИ НЕ должен отвечать в ЛС\n"
        "(например: @my_friend или просто my_friend):",
        reply_markup=cancel_flow_kb(),
    )


@router.message(AiSetup.exclude)
async def ai_skip_save(message: Message, state: FSMContext):
    from services import ai_replies
    from services.userbot import userbot as ub
    from utils.helpers import is_cancel

    if is_cancel(message.text):
        await state.clear()
        await message.answer("❌ Добавление отменено.")
        return
    username = (message.text or "").strip().lstrip("@")
    if not username or len(username) > 64:
        await message.answer("❌ Введите @username (до 64 символов):")
        return
    user_id = None
    if ub.is_connected:
        try:
            entity = await ub.client.get_entity(username)
            user_id = getattr(entity, "id", None)
        except Exception as e:
            logger.info("skip-add: не удалось resolve @%s: %s", username, e)
    await ai_replies.add_skip(user_id, username)
    await state.clear()
    await message.answer(
        f"✅ Добавлено: @{username}"
        + (f" (ID: <code>{user_id}</code>)" if user_id else "")
        + "\nИИ больше не будет отвечать этому человеку в ЛС."
    )


@router.callback_query(F.data == "admin:ai:test")
async def ai_test(callback: CallbackQuery):
    """Тестовый запрос к ИИ: сразу видно, работает ли ключ и модель."""
    if not await check_admin(callback):
        return
    if not config.AI_API_KEY:
        await callback.answer("AI_API_KEY не задан в .env", show_alert=True)
        return
    await callback.answer("Отправляю тестовый вопрос…")
    await callback.message.answer(
        f"🧪 Проверяю связь: <code>{config.AI_MODEL}</code>\n"
        f"через {config.AI_BASE_URL} …"
    )
    try:
        answer = await ai_assistant.answer_question(
            "Здравствуйте! Подскажите, сколько стоит занятие?"
        )
        await callback.message.answer(
            f"✅ <b>ИИ отвечает!</b>\n\n{answer}\n\n"
            f"<i>Это тестовый ответ по вашей анкете и FAQ.</i>"
        )
    except ai_assistant.AiUnavailable as e:
        await callback.message.answer(
            f"❌ <b>ИИ не ответил:</b> {e}\n\n"
            f"Проверьте:\n"
            f"— AI_API_KEY (для OpenRouter начинается с sk-or-)\n"
            f"— AI_BASE_URL (для OpenRouter: https://openrouter.ai/api/v1)\n"
            f"— AI_MODEL — точный ID с openrouter.ai/models, "
            f"например deepseek/deepseek-chat (без пробелов!)\n"
            f"— есть ли деньги/кредиты на балансе провайдера"
        )
