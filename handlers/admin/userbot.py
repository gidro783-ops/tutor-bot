# -*- coding: utf-8 -*-
"""Админка: userbot (рассылка от имени репетитора через Telethon).

Авторизация (в т.ч. 2FA), смена аккаунта, список чатов, добавление
по @username, рассылка с настраиваемой задержкой.
"""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import db
from keyboards.admin_kb import back_button
from keyboards.subscription_kb import cancel_flow_kb
from services.userbot import userbot
from utils.helpers import escape_html, is_cancel

from .core import check_admin, owner_id, upsell_kb
from services.cleanup import say

logger = logging.getLogger(__name__)
router = Router()

class UserbotLogin(StatesGroup):
    phone = State()
    code = State()
    password = State()  # v3: двухступенчатый пароль (2FA)
class UserbotAddChat(StatesGroup):
    username = State()
class UserbotMailing(StatesGroup):
    text = State()
    select_chats = State()
    confirm = State()

# =================== USERBOT: ГЛАВНОЕ МЕНЮ ===================
@router.callback_query(F.data == "admin:mail:userbot")
async def admin_userbot_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    # Доступно и на Free — лимит 10 сообщений/день проверяется при отправке
    if userbot.is_connected:
        me = None
        try:
            me = await userbot.client.get_me()
        except Exception:
            pass
        builder = InlineKeyboardBuilder()
        builder.button(text="💬 Список чатов", callback_data="ub:chats")
        builder.button(text="➕ Добавить по @username", callback_data="ub:add_chat:start")
        builder.button(text="📢 Рассылка от моего имени", callback_data="ub:mail:start")
        # v3: раньше сменить номер было невозможно — старая сессия
        # «закрывала» вход для любого другого аккаунта
        builder.button(text="🔄 Сменить аккаунт", callback_data="ub:switch")
        builder.button(text="🔌 Отключить", callback_data="ub:disconnect")
        builder.button(text="◀️ Назад", callback_data="admin:mailings")
        builder.adjust(1)
        name = escape_html(me.first_name) if me else "—"
        phone = me.phone if me else "—"
        await callback.message.edit_text(
            f"👤 <b>Userbot подключен</b>\n\n"
            f"📋 Аккаунт: {name}\n"
            f"📞 Телефон: {phone}\n\n"
            f"⚠️ Рассылка от вашего имени нарушает Telegram ToS!\n"
            f"⚠️ Риск ПЕРМАНЕНТНОГО БАНА аккаунта!",
            reply_markup=builder.as_markup(),
        )
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔑 Авторизоваться", callback_data="ub:login:start")
        builder.button(text="◀️ Назад", callback_data="admin:mailings")
        builder.adjust(1)
        await callback.message.edit_text(
            "👤 <b>Userbot не подключен</b>\n\n"
            "Для рассылки от имени репетитора нужно авторизоваться.\n\n"
            "Рекомендация: используйте рассылку от бота (безопасно).",
            reply_markup=builder.as_markup(),
        )
# =================== USERBOT: АВТОРИЗАЦИЯ ===================
@router.callback_query(F.data == "ub:login:start")
async def userbot_login_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    phone_hint = ""
    if userbot.phone:
        phone_hint = f"\n\n💡 Телефон из .env: <code>{userbot.phone}</code>\nОтправить код на него?"
    builder = InlineKeyboardBuilder()
    if userbot.phone:
        builder.button(
            text=f"📱 Отправить код на {userbot.phone}",
            callback_data="ub:login:env_phone",
        )
    builder.button(text="📱 Ввести другой номер", callback_data="ub:login:other_phone")
    builder.button(text="◀️ Отмена", callback_data="admin:mail:userbot")
    builder.adjust(1)
    await callback.message.edit_text(
        f"🔑 <b>Авторизация Userbot</b>\n\n"
        f"Введите номер телефона репетитора (с +7, +375 и т.д.)\n"
        f"Код подтверждения придёт в Telegram.{phone_hint}",
        reply_markup=builder.as_markup(),
    )
def _code_prompt_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📲 Прислать код по SMS", callback_data="ub:login:sms")
    builder.button(text="❌ Отмена", callback_data="cancel_flow")
    builder.adjust(1)
    return builder.as_markup()


CODE_HINT = (
    "\n\n⚠️ Вводите код из <b>последнего</b> сообщения Telegram — "
    "старые коды гаснут моментально."
)


@router.callback_query(F.data == "ub:login:env_phone")
async def userbot_login_env_phone(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    phone = userbot.phone
    ok, err = await userbot.send_code_request(phone)
    if ok:
        await state.update_data(
            phone=phone,
            phone_code_hash=userbot.phone_code_hash
        )
        await state.set_state(UserbotLogin.code)
        await callback.message.edit_text(
            f"📩 Код отправлен в Telegram на <code>{phone}</code>\n\n"
            f"Введите код подтверждения:" + CODE_HINT,
            reply_markup=_code_prompt_kb(),
        )
    else:
        # v3: показываем реальную причину, а не «Ошибка отправки кода»
        await callback.message.edit_text(f"❌ Не удалось отправить код:\n{escape_html(err)}")
@router.callback_query(F.data == "ub:login:other_phone")
async def userbot_login_other_phone(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(UserbotLogin.phone)
    await callback.message.edit_text(
        "📱 Введите номер телефона (например +79991234567):",
        reply_markup=cancel_flow_kb(),
    )
@router.message(UserbotLogin.phone)
async def userbot_login_phone(message: Message, state: FSMContext):
    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Авторизация отменена.")
        return
    phone = message.text.strip()
    if not phone.startswith("+"):
        # v3: подставляем + автоматически, если ученик-админ ввёл без него
        # (например 15551234567 для американского номера)
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) < 5:
            await say(message, "❌ Номер с + (например +79991234567):")
            return
        phone = "+" + digits
    ok, err = await userbot.send_code_request(phone)
    if ok:
        await state.update_data(
            phone=phone,
            phone_code_hash=userbot.phone_code_hash
        )
        await state.set_state(UserbotLogin.code)
        await say(message, 
            f"📩 Код отправлен в Telegram на номер {phone}\n\n"
            f"Введите 5-значный код подтверждения:" + CODE_HINT,
            reply_markup=_code_prompt_kb(),
        )
    else:
        # v3: реальная причина ошибки + можно попробовать снова
        await say(message, f"❌ {escape_html(err)}\n\nВведите номер ещё раз:")
@router.callback_query(F.data == "ub:login:sms")
async def userbot_login_sms(callback: CallbackQuery, state: FSMContext):
    """Повторная отправка кода СМС-кой: для +1 и подобных номеров
    код из приложения часто не совпадает с кодом для API-входа,
    а SMS-код — всегда рабочий."""
    if not await check_admin(callback):
        return
    data = await state.get_data()
    phone = data.get("phone") or userbot.phone
    if not phone:
        await callback.answer("Сначала запросите код", show_alert=True)
        return
    await callback.answer("Запрашиваю код по SMS…")
    ok, err = await userbot.send_code_request(phone, force_sms=True)
    if ok:
        await state.update_data(
            phone=phone, phone_code_hash=userbot.phone_code_hash
        )
        await state.set_state(UserbotLogin.code)
        await callback.message.answer(
            f"📲 Код отправлен СМС-кой на <code>{phone}</code>.\n"
            f"Введите код из СМС (придёт за 1-2 минуты):" + CODE_HINT,
            reply_markup=_code_prompt_kb(),
        )
    else:
        await callback.message.answer(
            f"❌ Не удалось отправить СМС:\n{escape_html(err)}\n\n"
            f"Попробуйте «🔑 Авторизоваться» ещё раз."
        )


@router.message(UserbotLogin.code)
async def userbot_login_code(message: Message, state: FSMContext):
    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Авторизация отменена.")
        return
    data = await state.get_data()
    phone = data.get("phone", "")
    phone_code_hash = data.get("phone_code_hash") or userbot.phone_code_hash
    raw = (message.text or "").strip()
    # Извлекаем только цифры (на случай пробелов, дефисов или текста)
    digits = "".join(c for c in raw if c.isdigit())
    code = digits if len(digits) >= 5 else raw
    ok, err = await userbot.sign_in(phone, code, phone_code_hash=phone_code_hash)
    if ok:
        await state.clear()
        me = None
        try:
            me = await userbot.client.get_me()
        except Exception:
            pass
        name = escape_html(me.first_name) if me else "—"
        await say(message, 
            f"✅ Userbot авторизован: {name}\n\n"
            f"Теперь можно делать рассылку от вашего имени.\n\n"
            f"⚠️ Помните о риске бана!"
        )
        await db.log_action(message.from_user.id, "userbot_authorized")
    elif err == "PASSWORD":
        # v3: аккаунт с двухступенчатым паролем (у нового/US-аккаунта
        # он включён по умолчанию в некоторых настройках)
        await state.update_data(phone=phone)
        await state.set_state(UserbotLogin.password)
        await say(message, 
            "🔐 У этого аккаунта включён двухступенчатый пароль.\n\n"
            "Введите пароль Telegram (не код, а тот, что задаётся в "
            "Настройки → Конфиденциальность → Дополнительный пароль):"
        )
    elif err == "CODE_EXPIRED":
        # Telegram прислал несколько кодов / повторный запрос погасил
        # старый. Не тупик: сами высылаем новый код.
        if phone:
            ok2, err2 = await userbot.send_code_request(phone)
            if ok2:
                await state.update_data(
                    phone=phone, phone_code_hash=userbot.phone_code_hash
                )
                await state.set_state(UserbotLogin.code)
                await say(message, 
                    "⌛ Этот код уже недействителен (обычно Telegram "
                    "присылал несколько кодов или код запрашивали "
                    "повторно).\n\n"
                    f"📩 Я отправил <b>новый код</b> на <code>{phone}</code> — "
                    f"введите код из ПОСЛЕДНЕГО сообщения:",
                    reply_markup=_code_prompt_kb(),
                )
                return
        await say(message, 
            "⌛ Код недействителен. Нажмите «🔑 Авторизоваться» — "
            "придёт новый код, и введите его сразу."
        )
    else:
        # v3: настоящая причина, а не «Неверный код»
        await say(message, f"❌ {escape_html(err)}\n\nВведите код ещё раз:")
@router.message(UserbotLogin.password)
async def userbot_login_password(message: Message, state: FSMContext):
    # v3: завершение входа для аккаунтов с 2FA
    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Авторизация отменена.")
        return
    ok, err = await userbot.finish_2fa(message.text.strip())
    if ok:
        await state.clear()
        me = None
        try:
            me = await userbot.client.get_me()
        except Exception:
            pass
        name = escape_html(me.first_name) if me else "—"
        await say(message, 
            f"✅ Userbot авторизован: {name}\n\n"
            f"Теперь можно делать рассылку от вашего имени.\n\n"
            f"⚠️ Помните о риске бана!"
        )
        await db.log_action(message.from_user.id, "userbot_authorized")
    else:
        await say(message, f"❌ {escape_html(err)}\n\nВведите пароль ещё раз:")
# ===== v3: СМЕНА АККАУНТА USERBOT =====
@router.callback_query(F.data == "ub:switch")
async def userbot_switch_ask(callback: CallbackQuery, state: FSMContext):
    # v3: прежде это было невозможно — сессия старым аккаунтом
    # блокировала привязку любого другого номера (US и др.)
    if not await check_admin(callback):
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, отвязать и сменить", callback_data="ub:switch:yes")
    builder.button(text="◀️ Отмена", callback_data="admin:mail:userbot")
    builder.adjust(1)
    await state.clear()
    await callback.message.edit_text(
        "🔄 <b>Смена аккаунта userbot</b>\n\n"
        "Текущая привязка будет удалена (файл сессии тоже), "
        "после этого можно ввести любой другой номер — в том числе "
        "американский +1... и т.д.\n\nПродолжить?",
        reply_markup=builder.as_markup(),
    )
@router.callback_query(F.data == "ub:switch:yes")
async def userbot_switch_do(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await userbot.reset_session()
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Ввести новый номер", callback_data="ub:login:other_phone")
    if userbot.phone:
        builder.button(
            text=f"📱 Отправить код на {userbot.phone}",
            callback_data="ub:login:env_phone",
        )
    builder.button(text="◀️ Назад", callback_data="admin:mail:userbot")
    builder.adjust(1)
    await callback.message.edit_text(
        "🧹 Старый аккаунт отвязан.\n\nТеперь введите номер нового аккаунта:",
        reply_markup=builder.as_markup(),
    )
@router.callback_query(F.data == "ub:disconnect")
async def userbot_disconnect(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    # v3: «Отключить» теперь удаляет и файл сессии — иначе при следующем
    # запуске бота старый аккаунт подключался обратно сам
    await userbot.reset_session()
    await callback.message.edit_text(
        "🔌 Userbot отключен, старая сессия удалена."
    )
    await db.log_action(callback.from_user.id, "userbot_disconnected")
# =================== USERBOT: СПИСОК ЧАТОВ ===================
@router.callback_query(F.data == "ub:chats")
async def userbot_chats(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    if not userbot.is_connected:
        await callback.answer("Сначала авторизуйтесь", show_alert=True)
        return
    chats = await userbot.get_chats(limit=50)
    if not chats:
        await callback.message.edit_text(
            "📭 Чаты не найдены.\n\nПопробуйте добавить по @username →",
            reply_markup=back_button("admin:mail:userbot"),
        )
        return
    text = "💬 <b>Ваши чаты и каналы:</b>\n\n"
    for c in chats[:30]:
        icon = "📢" if c["type"] == "Канал" else "💬"
        uname = f" @{c['username']}" if c.get("username") else ""
        members = c.get("members", "?")
        text += f"{icon} {escape_html(c['title'])}{uname} — {members} чел.\n"
    text += f"\n📊 Всего: {len(chats)}"
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить по @username", callback_data="ub:add_chat:start")
    builder.button(text="◀️ Назад", callback_data="admin:mail:userbot")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
# =================== USERBOT: ДОБАВИТЬ ЧАТ ПО @USERNAME ===================
@router.callback_query(F.data == "ub:add_chat:start")
async def userbot_add_chat_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    if not userbot.is_connected:
        await callback.answer("Сначала авторизуйтесь", show_alert=True)
        return
    await state.set_state(UserbotAddChat.username)
    await callback.message.edit_text(
        "➕ <b>Добавить чат по @username</b>\n\n"
        "Введите username чата или канала:\n"
        "• @my_channel\n"
        "• my_channel (без @ тоже работает)\n\n"
        "Работает только для <b>публичных</b> групп и каналов.",
        reply_markup=cancel_flow_kb(),
    )
@router.message(UserbotAddChat.username)
async def userbot_add_chat_username(message: Message, state: FSMContext):
    if is_cancel(message.text):
        await state.clear()
        await message.answer("❌ Добавление чата отменено.")
        return
    username = message.text.strip().lstrip("@")
    if not username:
        await message.answer("❌ Введите username (например @my_channel):")
        return
    await message.answer("🔍 Ищу чат/канал...")
    chat = await userbot.get_chat_by_username(username)
    if chat:
        try:
            await db.add_ad_chat(chat["id"], chat["title"])
        except Exception as e:
            logger.warning(f"Failed to save chat to DB: {e}")
        await state.clear()
        uname = f"@{chat['username']}" if chat.get("username") else "приватный"
        members = chat.get("members", "?")
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить ещё", callback_data="ub:add_chat:start")
        builder.button(text="📢 Начать рассылку", callback_data="ub:mail:start")
        builder.button(text="◀️ Назад", callback_data="admin:mail:userbot")
        builder.adjust(1)
        await message.answer(
            f"✅ <b>Чат найден и добавлен!</b>\n\n"
            f"💬 Название: {escape_html(chat['title'])}\n"
            f"📋 Тип: {chat['type']}\n"
            f"🔗 Username: {uname}\n"
            f"👥 Участников: {members}\n"
            f"🆔 ID: <code>{chat['id']}</code>",
            reply_markup=builder.as_markup(),
        )
    else:
        await message.answer(
            f"❌ Чат <code>@{escape_html(username)}</code> не найден.\n\n"
            f"Возможные причины:\n"
            f"• Канал приватный (нет @username)\n"
            f"• Опечатка в username\n"
            f"• У репетитора нет доступа к этому чату\n\n"
            f"Попробуйте ещё раз или введите другой:"
        )
# =================== USERBOT: РАССЫЛКА ===================
@router.callback_query(F.data == "ub:mail:start")
async def userbot_mailing_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    if not userbot.is_connected:
        await callback.answer("Сначала авторизуйтесь", show_alert=True)
        return
    await state.set_state(UserbotMailing.text)
    await callback.message.edit_text(
        "📢 <b>Рассылка от имени репетитора</b>\n\n"
        "Введите текст рассылки:\n\n"
        "⚠️ Сообщения отправляются с задержкой 5-30 сек между чатами.",
        reply_markup=cancel_flow_kb(),
    )
@router.message(UserbotMailing.text)
async def userbot_mailing_text(message: Message, state: FSMContext):
    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Рассылка отменена.")
        return
    text = message.text
    if not text or len(text) > 4096:
        await say(message, "❌ Текст от 1 до 4096 символов:")
        return
    await state.update_data(mail_text=text, selected_chats=[])
    chats = await userbot.get_chats(limit=50)
    if not chats:
        await state.clear()
        await say(message, "❌ Нет доступных чатов. Добавьте по @username.")
        return
    db_chats = await db.get_ad_chats()
    all_chats = list(chats)
    for dc in db_chats:
        if dc["chat_id"] not in {c["id"] for c in all_chats}:
            all_chats.append({
                "id": dc["chat_id"],
                "title": dc.get("chat_title", "—"),
                "username": None,
                "type": "Чат",
                "members": 0,
            })
    chat_map = {c["id"]: c for c in all_chats}
    await state.update_data(chat_map=chat_map)
    await state.set_state(UserbotMailing.select_chats)
    await _show_chat_selection(message, all_chats, [])
async def _show_chat_selection(target, all_chats: list, selected_ids: list):
    builder = InlineKeyboardBuilder()
    for c in all_chats[:25]:
        is_selected = c["id"] in selected_ids
        check = "✅" if is_selected else "☐"
        icon = "📢" if c.get("type") == "Канал" else "💬"
        members = c.get("members", "?")
        uname = f" @{c['username']}" if c.get("username") else ""
        title = c["title"][:20]
        builder.button(
            text=f"{check} {icon} {title}{uname} ({members})",
            callback_data=f"ub:sel:{c['id']}",
        )
    if selected_ids:
        builder.button(
            text=f"✅ Отправить ({len(selected_ids)} чатов)",
            callback_data="ub:mail:confirm",
        )
    builder.button(text="✅ Отправить во ВСЕ", callback_data="ub:mail:all")
    builder.button(text="❌ Отмена", callback_data="ub:mail:cancel")
    builder.adjust(1)
    text = (
        f"📢 <b>Выберите чаты для рассылки</b>\n\n"
        f"Нажмите на чат, чтобы добавить/убрать.\n"
        f"Выбрано: <b>{len(selected_ids)}</b> из {len(all_chats)}\n\n"
        f"Нажмите «Отправить» когда выберите."
    )
    await target.answer(text, reply_markup=builder.as_markup())
@router.callback_query(F.data.startswith("ub:sel:"))
async def userbot_toggle_chat(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    selected = data.get("selected_chats", [])
    chat_map = data.get("chat_map", {})
    if chat_id in selected:
        selected.remove(chat_id)
    else:
        selected.append(chat_id)
    await state.update_data(selected_chats=selected)
    all_chats = list(chat_map.values())
    await _show_chat_selection(callback.message, all_chats, selected)
@router.callback_query(F.data == "ub:mail:all")
async def userbot_mail_all(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mail_text = data.get("mail_text", "")
    chat_map = data.get("chat_map", {})
    chat_ids = list(chat_map.keys())
    await state.update_data(selected_chats=chat_ids)
    await _show_delay_choice(callback, len(chat_ids), mail_text)
    return
UB_DELAYS = [
    ("⚡ 10 сек", 10),
    ("🚶 30 сек", 30),
    ("🕐 1 мин", 60),
    ("🕔 5 мин", 300),
    ("🕝 15 мин", 900),
    ("🕧 30 мин", 1800),
    ("🐢 1 час", 3600),
    ("🐌 2 часа", 7200),
]
def _fmt_delay(sec: int) -> str:
    if sec >= 3600:
        return f"{sec / 3600:g} ч"
    if sec >= 60:
        return f"{sec // 60} мин"
    return f"{sec} сек"
def _fmt_eta(total_sec: int) -> str:
    if total_sec >= 3600:
        return f"~{total_sec / 3600:.1f} ч"
    if total_sec >= 60:
        return f"~{total_sec // 60} мин"
    return f"~{total_sec} сек"
async def _show_delay_choice(callback: CallbackQuery, count: int, mail_text: str):
    builder = InlineKeyboardBuilder()
    for label, sec in UB_DELAYS:
        builder.button(text=label, callback_data=f"ub:delay:{sec}")
    builder.button(text="❌ Отмена", callback_data="ub:mail:cancel")
    builder.adjust(2)
    await callback.message.edit_text(
        f"📢 <b>Рассылка от имени репетитора</b>\n\n"
        f"💬 Выбрано чатов: {count}\n"
        f"📝 Текст: {escape_html(mail_text[:200])}\n\n"
        f"⏱ <b>Выберите задержку между сообщениями:</b>\n"
        f"Чем больше пауза — тем ниже риск бана аккаунта.\n"
        f"Для безопасности рекомендуется от 15 минут.",
        reply_markup=builder.as_markup(),
    )

@router.callback_query(F.data == "ub:mail:confirm")
async def userbot_mail_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mail_text = data.get("mail_text", "")
    selected = data.get("selected_chats", [])
    if not selected:
        await callback.answer("Выберите хотя бы один чат!", show_alert=True)
        return
    await _show_delay_choice(callback, len(selected), mail_text)


@router.callback_query(F.data.startswith("ub:delay:"))
async def userbot_choose_delay(callback: CallbackQuery, state: FSMContext):
    delay = int(callback.data.split(":")[-1])
    await state.update_data(ub_delay=delay)
    await state.set_state(UserbotMailing.confirm)
    data = await state.get_data()
    mail_text = data.get("mail_text", "")
    selected = data.get("selected_chats", [])
    eta = _fmt_eta(max(0, len(selected) - 1) * delay)
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="ub:mail:send")
    builder.button(text="⏱ Другая задержка", callback_data="ub:mail:confirm")
    builder.button(text="❌ Отмена", callback_data="ub:mail:cancel")
    builder.adjust(1)
    await callback.message.edit_text(
        f"📢 <b>Рассылка от имени репетитора</b>\n\n"
        f"💬 Чатов: {len(selected)}\n"
        f"📝 Текст: {escape_html(mail_text[:300])}\n"
        f"⏱ Задержка: <b>{_fmt_delay(delay)}</b> между сообщениями\n"
        f"🕓 Общее время: {eta}\n\n"
        f"Подтвердите отправку:",
        reply_markup=builder.as_markup(),
    )

@router.callback_query(F.data == "ub:mail:send")
async def userbot_mail_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mail_text = data.get("mail_text", "")
    chat_ids = data.get("selected_chats", [])
    delay = data.get("ub_delay", 30)
    await state.clear()
    if not chat_ids or not mail_text:
        await callback.message.edit_text("❌ Нет данных для рассылки.")
        return
    # Тарифный лимит Free: N сообщений в день
    from services import subscription as sub_service

    owner = owner_id()
    if owner is not None:
        left = await sub_service.mailing_left_today(owner)
        if left is not None and len(chat_ids) > left:
            await callback.message.edit_text(
                f"🚫 <b>Лимит бесплатного тарифа</b>\n\n"
                f"Сегодня можно отправить ещё {left} сообщений, "
                f"а выбрано чатов — {len(chat_ids)}.\n\n"
                f"PRO (990 ₽/мес) снимает лимиты. "
                f"Или начните с 7 бесплатных дней 👇",
                reply_markup=await upsell_kb(),
            )
            return
    await callback.message.edit_text(
        f"📤 <b>Рассылка идёт...</b>\n\n"
        f"💬 Чатов: {len(chat_ids)}\n"
        f"⏳ Это может занять несколько минут"
    )
    result = await userbot.send_mailing_to_chats(
        chat_ids=chat_ids,
        text=mail_text,
        delay_between=float(delay),
    )
    sent = result["sent"]
    errors = result["errors"]
    if owner is not None and sent:
        await sub_service.consume_mailing(owner, sent)
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ К рассылкам", callback_data="admin:mailings")
    builder.adjust(1)
    await callback.message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Доставлено: {sent}\n"
        f"❌ Ошибок: {errors}\n"
        f"💬 Всего чатов: {len(chat_ids)}",
        reply_markup=builder.as_markup(),
    )
    await db.log_action(
        callback.from_user.id,
        "userbot_mailing",
        {"sent": sent, "errors": errors, "total": len(chat_ids)},
    )
@router.callback_query(F.data == "ub:mail:cancel")
async def userbot_mail_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена.")
