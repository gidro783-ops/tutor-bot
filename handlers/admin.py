from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from config import config
from database import db
from keyboards.admin_kb import (
    admin_main_menu, admin_students_menu, admin_schedule_menu,
    admin_subjects_menu, admin_homework_menu, admin_payments_menu,
    admin_mailings_menu, admin_faq_menu, admin_analytics_menu,
    admin_dnd_menu, confirm_keyboard, back_button,
    student_list_keyboard, student_detail_keyboard
)
from utils.texts import Texts
from utils.helpers import format_date, escape_html
from services.userbot import userbot
import logging
logger = logging.getLogger(__name__)
router = Router()
# =================== RATE LIMITING ===================
_failed_attempts: dict[int, int] = {}
_locked_until: dict[int, datetime] = {}
def _is_locked(admin_id: int) -> bool:
    lock = _locked_until.get(admin_id)
    if lock and datetime.now() < lock:
        return True
    if lock and datetime.now() >= lock:
        _failed_attempts[admin_id] = 0
        del _locked_until[admin_id]
    return False
# =================== FSM ===================
class AdminAuth(StatesGroup):
    waiting_password = State()
class AddSubject(StatesGroup):
    name = State()
    price = State()
    description = State()
class AddSlot(StatesGroup):
    date = State()
    start_time = State()
    end_time = State()
class AddFAQ(StatesGroup):
    question = State()
    answer = State()
    keywords = State()
class AddHomework(StatesGroup):
    student_id = State()
    subject_id = State()
    title = State()
    description = State()
    due_date = State()
    files = State()
class CreatePayment(StatesGroup):
    student_id = State()
    amount = State()
    description = State()
class GradeHomework(StatesGroup):
    hw_id = State()
    grade = State()
    feedback = State()
class NewMailing(StatesGroup):
    text = State()
    target = State()
    confirm = State()
class SendMessage(StatesGroup):
    student_id = State()
    message = State()
class DndSetup(StatesGroup):
    start_time = State()
    end_time = State()
    auto_reply = State()
class AddAdChat(StatesGroup):
    chat_id = State()
    chat_title = State()
class ABTestSetup(StatesGroup):
    name = State()
    variant_a = State()
    variant_b = State()
class UserbotLogin(StatesGroup):
    phone = State()
    code = State()
class UserbotAddChat(StatesGroup):
    username = State()
class UserbotMailing(StatesGroup):
    text = State()
    select_chats = State()
    confirm = State()
# =================== АВТОРИЗАЦИЯ ===================
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer(Texts.ADMIN_NOT_AUTHORIZED)
        await db.log_action(message.from_user.id, "unauthorized_admin_attempt")
        return
    if await db.check_admin_session(message.from_user.id):
        await show_admin_panel(message)
        return
    await state.set_state(AdminAuth.waiting_password)
    await message.answer(Texts.ADMIN_CMD)
@router.message(AdminAuth.waiting_password)
async def process_password(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS:
        await state.clear()
        return
    try:
        await message.delete()
    except Exception:
        pass
    admin_id = message.from_user.id
    if _is_locked(admin_id):
        lock = _locked_until[admin_id]
        remaining = int((lock - datetime.now()).total_seconds() / 60) + 1
        await message.answer(
            f"🔒 Слишком много попыток. Попробуйте через {remaining} мин."
        )
        return
    if message.text == config.ADMIN_PASSWORD:
        _failed_attempts[admin_id] = 0
        _locked_until.pop(admin_id, None)
        await db.authenticate_admin(admin_id, hours=12)
        await db.log_action(admin_id, "admin_login")
        await state.clear()
        await message.answer(Texts.ADMIN_SUCCESS)
        await show_admin_panel(message)
    else:
        _failed_attempts[admin_id] = _failed_attempts.get(admin_id, 0) + 1
        remaining = config.ADMIN_MAX_FAILED_ATTEMPTS - _failed_attempts[admin_id]
        if remaining <= 0:
            _locked_until[admin_id] = datetime.now() + timedelta(
                minutes=config.ADMIN_LOCK_MINUTES
            )
            await message.answer(
                f"🔒 Слишком много неверных попыток. "
                f"Аккаунт заблокирован на {config.ADMIN_LOCK_MINUTES} мин."
            )
            await db.log_action(admin_id, "admin_locked_out")
        else:
            await message.answer(
                f"❌ Неверный пароль. Осталось попыток: {remaining}"
            )
            await db.log_action(admin_id, "admin_wrong_password")
async def show_admin_panel(message: Message):
    stats = await db.get_dashboard_stats()
    text = Texts.ADMIN_PANEL.format(**stats)
    await message.answer(text, reply_markup=admin_main_menu())
async def check_admin(callback: CallbackQuery) -> bool:
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer(Texts.ADMIN_NOT_AUTHORIZED, show_alert=True)
        return False
    if not await db.check_admin_session(callback.from_user.id):
        await callback.answer(Texts.ADMIN_SESSION_EXPIRED, show_alert=True)
        return False
    return True
# =================== НАВИГАЦИЯ ===================
@router.callback_query(F.data == "admin:back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.clear()
    stats = await db.get_dashboard_stats()
    text = Texts.ADMIN_PANEL.format(**stats)
    await callback.message.edit_text(text, reply_markup=admin_main_menu())
@router.callback_query(F.data == "admin:logout")
async def admin_logout(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await db.logout_admin(callback.from_user.id)
    await db.log_action(callback.from_user.id, "admin_logout")
    await state.clear()
    await callback.message.edit_text("👋 Вы вышли из админ-панели.")
# =================== УЧЕНИКИ ===================
@router.callback_query(F.data == "admin:students")
async def admin_students(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "👥 <b>Управление учениками</b>",
        reply_markup=admin_students_menu(),
    )
@router.callback_query(F.data == "admin:students:list")
async def admin_students_list(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    students_list = await db.get_all_students()
    if not students_list:
        await callback.message.edit_text(
            "📭 Учеников пока нет.",
            reply_markup=back_button("admin:students"),
        )
        return
    await callback.message.edit_text(
        f"👥 Всего учеников: {len(students_list)}",
        reply_markup=student_list_keyboard(students_list),
    )
@router.callback_query(F.data.startswith("admin:students:page:"))
async def admin_students_page(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    page = int(callback.data.split(":")[-1])
    students_list = await db.get_all_students()
    await callback.message.edit_text(
        f"👥 Всего учеников: {len(students_list)}",
        reply_markup=student_list_keyboard(students_list, page=page),
    )
@router.callback_query(
    F.data.startswith("admin:student:")
    & ~F.data.contains(":bookings")
    & ~F.data.contains(":hw")
    & ~F.data.contains(":payments")
    & ~F.data.contains(":message")
    & ~F.data.contains(":deactivate")
)
async def admin_student_detail(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    student_id = int(callback.data.split(":")[2])
    student = await db.get_student(student_id)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return
    bookings = await db.get_student_bookings(student_id)
    pending_payments = await db.get_pending_payments(student_id)
    text = (
        f"👤 <b>{escape_html(student['full_name'])}</b>\n\n"
        f"🆔 ID: <code>{student['user_id']}</code>\n"
        f"📱 @{escape_html(student.get('username') or '—')}\n"
        f"📞 {escape_html(student.get('phone') or '—')}\n"
        f"📅 {student['registration_date'][:10]}\n"
        f"📊 Занятий: {student.get('total_lessons', 0)}\n"
        f"📌 Источник: {student.get('source', '—')}\n"
        f"📋 Записей: {len(bookings)}\n"
        f"💳 Долг: {len(pending_payments)}\n"
        f"📝 {escape_html(student.get('notes', '—'))}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=student_detail_keyboard(student_id),
    )
# =================== ПРЕДМЕТЫ ===================
@router.callback_query(F.data == "admin:subjects")
async def admin_subjects(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📚 <b>Предметы</b>",
        reply_markup=admin_subjects_menu(),
    )
@router.callback_query(F.data == "admin:subjects:list")
async def admin_subjects_list(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    subjects_list = await db.get_subjects()
    if not subjects_list:
        await callback.message.edit_text(
            "📭 Предметов нет.",
            reply_markup=back_button("admin:subjects"),
        )
        return
    text = "📚 <b>Предметы:</b>\n\n"
    for s in subjects_list:
        status = "✅" if s.get("is_active") else "❌"
        text += f"{status} {escape_html(s['name'])} — {s.get('price_per_hour', 0)}₽/ч\n"
    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:subjects"),
    )
@router.callback_query(F.data == "admin:subjects:add")
async def admin_add_subject(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(AddSubject.name)
    await callback.message.edit_text("📚 Название предмета:")
@router.message(AddSubject.name)
async def add_subject_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) > 200:
        await message.answer("❌ Название от 1 до 200 символов:")
        return
    await state.update_data(name=name)
    await state.set_state(AddSubject.price)
    await message.answer("💰 Цена за час (число):")
@router.message(AddSubject.price)
async def add_subject_price(message: Message, state: FSMContext):
    from utils.helpers import validate_amount
    try:
        price = validate_amount(message.text)
    except ValueError as e:
        await message.answer(f"❌ {e}\n\nЕщё раз:")
        return
    await state.update_data(price=price)
    await state.set_state(AddSubject.description)
    await message.answer("📋 Описание (или «-» без описания):")
@router.message(AddSubject.description)
async def add_subject_description(message: Message, state: FSMContext):
    data = await state.get_data()
    desc = "" if message.text.strip() == "-" else message.text.strip()
    try:
        await db.add_subject(name=data["name"], price=data["price"], description=desc)
        await state.clear()
        await message.answer(f"✅ Предмет <b>{escape_html(data['name'])}</b> добавлен!")
    except Exception as e:
        logger.error(f"Failed to add subject: {e}")
        await state.clear()
        await message.answer("❌ Ошибка. Возможно, предмет уже существует.")
# =================== РАСПИСАНИЕ ===================
@router.callback_query(F.data == "admin:schedule")
async def admin_schedule(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📅 <b>Расписание</b>",
        reply_markup=admin_schedule_menu(),
    )
@router.callback_query(F.data == "admin:schedule:today")
async def admin_schedule_today(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    from datetime import date as date_type
    today = date_type.today().isoformat()
    slots = await db.get_slots_for_date(today)
    if not slots:
        await callback.message.edit_text(
            f"📭 На сегодня ({format_date(today)}) слотов нет.",
            reply_markup=back_button("admin:schedule"),
        )
        return
    text = f"📅 <b>Сегодня ({format_date(today)}):</b>\n\n"
    for s in slots:
        status = "✅" if s["is_available"] else "🔒"
        text += f"{status} {s['start_time'][:5]}—{s['end_time'][:5]}\n"
    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:schedule"),
    )
# =================== РАССЫЛКИ ===================
@router.callback_query(F.data == "admin:mailings")
async def admin_mailings(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📢 <b>Рассылки</b>",
        reply_markup=admin_mailings_menu(),
    )
# =================== USERBOT: ГЛАВНОЕ МЕНЮ ===================
@router.callback_query(F.data == "admin:mail:userbot")
async def admin_userbot_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
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
@router.callback_query(F.data == "ub:login:env_phone")
async def userbot_login_env_phone(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    phone = userbot.phone
    success = await userbot.send_code_request(phone)
    if success:
        await state.update_data(phone=phone)
        await state.set_state(UserbotLogin.code)
        await callback.message.edit_text(
            f"📩 Код отправлен на <code>{phone}</code>\n\nВведите код подтверждения:"
        )
    else:
        await callback.message.edit_text("❌ Ошибка отправки кода. Проверьте телефон в .env.")
@router.callback_query(F.data == "ub:login:other_phone")
async def userbot_login_other_phone(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(UserbotLogin.phone)
    await callback.message.edit_text("📱 Введите номер телефона (например +79991234567):")
@router.message(UserbotLogin.phone)
async def userbot_login_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("❌ Номер с + (например +79991234567):")
        return
    success = await userbot.send_code_request(phone)
    if success:
        await state.update_data(phone=phone)
        await state.set_state(UserbotLogin.code)
        await message.answer(f"📩 Код отправлен на {phone}\n\nВведите код:")
    else:
        await state.clear()
        await message.answer("❌ Ошибка отправки кода. Проверьте номер.")
@router.message(UserbotLogin.code)
async def userbot_login_code(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = data.get("phone", "")
    code = message.text.strip()
    success = await userbot.sign_in(phone, code)
    if success:
        await state.clear()
        me = None
        try:
            me = await userbot.client.get_me()
        except Exception:
            pass
        name = escape_html(me.first_name) if me else "—"
        await message.answer(
            f"✅ Userbot авторизован: {name}\n\n"
            f"Теперь можно делать рассылку от вашего имени.\n\n"
            f"⚠️ Помните о риске бана!"
        )
        await db.log_action(message.from_user.id, "userbot_authorized")
    else:
        await message.answer("❌ Неверный код. Попробуйте ещё раз:")
@router.callback_query(F.data == "ub:disconnect")
async def userbot_disconnect(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await userbot.disconnect()
    await callback.message.edit_text("🔌 Userbot отключен.")
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
        "Работает только для <b>публичных</b> групп и каналов."
    )
@router.message(UserbotAddChat.username)
async def userbot_add_chat_username(message: Message, state: FSMContext):
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
        "⚠️ Сообщения отправляются с задержкой 5-30 сек между чатами."
    )
@router.message(UserbotMailing.text)
async def userbot_mailing_text(message: Message, state: FSMContext):
    text = message.text
    if not text or len(text) > 4096:
        await message.answer("❌ Текст от 1 до 4096 символов:")
        return
    await state.update_data(mail_text=text, selected_chats=[])
    chats = await userbot.get_chats(limit=50)
    if not chats:
        await state.clear()
        await message.answer("❌ Нет доступных чатов. Добавьте по @username.")
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
    await state.set_state(UserbotMailing.confirm)
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="ub:mail:send")
    builder.button(text="❌ Отмена", callback_data="ub:mail:cancel")
    builder.adjust(2)
    await callback.message.edit_text(
        f"📢 <b>Рассылка от имени репетитора</b>\n\n"
        f"💬 Чатов: {len(chat_ids)}\n"
        f"📝 Текст: {escape_html(mail_text[:300])}\n\n"
        f"⏱ Примерное время: ~{len(chat_ids) * 20} сек\n\n"
        f"Подтвердите отправку:",
        reply_markup=builder.as_markup(),
    )
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

async def userbot_mail_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mail_text = data.get("mail_text", "")
    selected = data.get("selected_chats", [])
    if not selected:
        await callback.answer("Выберите хотя бы один чат!", show_alert=True)
        return
    await state.set_state(UserbotMailing.confirm)
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="ub:mail:send")
    builder.button(text="❌ Отмена", callback_data="ub:mail:cancel")
    builder.adjust(2)
    await callback.message.edit_text(
        f"📢 <b>Рассылка от имени репетитора</b>\n\n"
        f"💬 Выбрано чатов: {len(selected)}\n"
        f"📝 Текст: {escape_html(mail_text[:300])}\n\n"
        f"⏱ Примерное время: ~{len(selected) * 20} сек\n\n"
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
# =================== DND ===================
@router.callback_query(F.data == "admin:dnd")
async def admin_dnd(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "🔕 <b>Режим «Не беспокоить»</b>",
        reply_markup=admin_dnd_menu(),
    )
@router.callback_query(F.data == "admin:dnd:enable")
async def admin_dnd_enable(callback: CallbackQuery):
    # ИСПРАВЛЕНО: убрана сломанная конструкция из двух строк, из-за которой
    # кнопка «Включить DND» работала некорректно
    if not await check_admin(callback):
        return
    await db.set_dnd(True)
    start = await db.get_setting("dnd_start", config.DND_START)
    end = await db.get_setting("dnd_end", config.DND_END)
    await callback.message.edit_text(
        f"✅ <b>DND включён.</b>\n\n"
        f"⏰ Окно: {start} — {end} ({config.TIMEZONE})\n"
        f"В это время бот не отвечает ученикам "
        f"и присылает автоответ.",
        reply_markup=admin_dnd_menu(),
    )
@router.callback_query(F.data == "admin:dnd:disable")
async def admin_dnd_disable(callback: CallbackQuery):
    # ИСПРАВЛЕНО: аналогично кнопке включения
    if not await check_admin(callback):
        return
    await db.set_dnd(False)
    await callback.message.edit_text(
        "🔔 <b>DND выключен.</b>\n\nБот снова отвечает ученикам.",
        reply_markup=admin_dnd_menu(),
    )
# =================== ОПЛАТЫ ===================
@router.callback_query(F.data == "admin:payments")
async def admin_payments(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "💳 <b>Оплаты</b>",
        reply_markup=admin_payments_menu(),
    )
# =================== FAQ ===================
@router.callback_query(F.data == "admin:faq")
async def admin_faq(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "❓ <b>FAQ</b>",
        reply_markup=admin_faq_menu(),
    )
# =================== АНАЛИТИКА ===================
@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    try:
        from services.analytics_service import AnalyticsService
        report = await AnalyticsService.get_full_report(period_days=30)
        text = await AnalyticsService.format_report(report)
        await callback.message.edit_text(text, reply_markup=back_button("admin:back"))
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== РЕФЕРАЛЫ ===================
@router.callback_query(F.data == "admin:referrals")
async def admin_referrals(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    try:
        referrals = await db.get_all_referrals()
        if not referrals:
            await callback.message.edit_text(
                "🎁 Рефералов нет.",
                reply_markup=back_button("admin:back"),
            )
            return
        text = f"🎁 <b>Рефералы</b> (скидка {config.REFERRAL_BONUS_PERCENT}%)\n\n"
        for r in referrals[:10]:
            status_emoji = {"pending": "⏳", "completed": "✅", "expired": "⌛"}
            text += (
                f"{status_emoji.get(r['status'], '❔')} "
                f"<code>{r['referral_code']}</code> — {r['status']}\n"
            )
        await callback.message.edit_text(text, reply_markup=back_button("admin:back"))
    except Exception as e:
        logger.error(f"Referral error: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== ОТЗЫВЫ ===================
@router.callback_query(F.data == "admin:reviews")
async def admin_reviews(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    try:
        all_reviews = await db.get_all_reviews()
        if not all_reviews:
            await callback.message.edit_text(
                "⭐ Отзывов нет.",
                reply_markup=back_button("admin:back"),
            )
            return
        avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
        text = f"⭐ <b>Отзывы</b> (средний: {avg:.1f}/5)\n\n"
        for r in all_reviews[:10]:
            text += f"{'⭐' * r['rating']} {escape_html(r.get('text', '')[:50])}\n"
        await callback.message.edit_text(text, reply_markup=back_button("admin:back"))
    except Exception as e:
        logger.error(f"Reviews error: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== НАСТРОЙКИ ===================
@router.callback_query(F.data == "admin:settings")
async def admin_settings(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    ub_status = "✅ Подключен" if userbot.is_connected else "❌ Не подключен"
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🌍 Таймзона: {config.TIMEZONE}\n"
        f"🔕 DND: {config.DND_START}—{config.DND_END}\n"
        f"🔔 Напоминания: за {', '.join(str(m) + ' мин' for m in config.REMINDER_BEFORE_MINUTES)}\n"
        f"📢 Макс. рассылок/день: {config.MAX_MAILING_PER_DAY}\n"
        f"🎁 Реферальная скидка: {config.REFERRAL_BONUS_PERCENT}%\n"
        f"🔒 Rate limit: {config.ADMIN_MAX_FAILED_ATTEMPTS} попыток, "
        f"блок {config.ADMIN_LOCK_MINUTES} мин\n"
        f"👤 Userbot: {ub_status}"
    )
    await callback.message.edit_text(text, reply_markup=back_button("admin:back"))
