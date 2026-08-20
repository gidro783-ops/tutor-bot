from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

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
from utils.helpers import format_date

router = Router()


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

class UserbotMailing(StatesGroup):
    select_chat = State()
    text = State()
    schedule_type = State()
    schedule_time = State()


# =================== АВТОРИЗАЦИЯ ===================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Команда входа в админ-панель — только для ID из списка."""
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer(Texts.ADMIN_NOT_AUTHORIZED)
        await db.log_action(
            message.from_user.id, "unauthorized_admin_attempt"
        )
        return

    # Проверяем, есть ли активная сессия
    if await db.check_admin_session(message.from_user.id):
        await show_admin_panel(message)
        return

    await state.set_state(AdminAuth.waiting_password)
    await message.answer(Texts.ADMIN_CMD)


@router.message(AdminAuth.waiting_password)
async def process_password(message: Message, state: FSMContext):
    """Проверка пароля администратора."""
    if message.from_user.id not in config.ADMIN_IDS:
        await state.clear()
        return

    # Удаляем сообщение с паролем для безопасности
    try:
        await message.delete()
    except Exception:
        pass

    if message.text == config.ADMIN_PASSWORD:
        await db.authenticate_admin(message.from_user.id, hours=12)
        await db.log_action(message.from_user.id, "admin_login")
        await state.clear()
        await message.answer(Texts.ADMIN_SUCCESS)
        await show_admin_panel(message)
    else:
        await message.answer(Texts.ADMIN_WRONG_PASSWORD)
        await db.log_action(
            message.from_user.id, "admin_wrong_password"
        )


async def show_admin_panel(message: Message):
    """Показать главное меню админ-панели с дашбордом."""
    stats = await db.get_dashboard_stats()
    text = Texts.ADMIN_PANEL.format(**stats)
    await message.answer(text, reply_markup=admin_main_menu(),
                         parse_mode="Markdown")


async def check_admin(callback: CallbackQuery) -> bool:
    """Проверка авторизации админа для callback."""
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
    await callback.message.edit_text(text, reply_markup=admin_main_menu(),
                                     parse_mode="Markdown")


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
        "👥 **Управление учениками**",
        reply_markup=admin_students_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:students:list")
async def admin_students_list(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    students = await db.get_all_students()
    if not students:
        await callback.message.edit_text(
            "📭 Учеников пока нет.",
            reply_markup=back_button("admin:students")
        )
        return
    await callback.message.edit_text(
        f"👥 Всего учеников: {len(students)}",
        reply_markup=student_list_keyboard(students)
    )


@router.callback_query(F.data.startswith("admin:students:page:"))
async def admin_students_page(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    page = int(callback.data.split(":")[-1])
    students = await db.get_all_students()
    await callback.message.edit_text(
        f"👥 Всего учеников: {len(students)}",
        reply_markup=student_list_keyboard(students, page=page)
    )


@router.callback_query(F.data.startswith("admin:student:") & ~F.data.contains(":bookings") & ~F.data.contains(":hw") & ~F.data.contains(":payments") & ~F.data.contains(":message") & ~F.data.contains(":deactivate"))
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
        f"👤 **{student['full_name']}**\n\n"
        f"🆔 ID: `{student['user_id']}`\n"
        f"📱 Username: @{student.get('username', '—')}\n"
        f"📞 Телефон: {student.get('phone', '—')}\n"
        f"📅 Зарегистрирован: {student['registration_date'][:10]}\n"
        f"🔄 Последняя активность: {student.get('last_activity', '—')}\n"
        f"📊 Всего занятий: {student.get('total_lessons', 0)}\n"
        f"📌 Источник: {student.get('source', '—')}\n"
        f"📋 Записей: {len(bookings)}\n"
        f"💳 Неоплаченных: {len(pending_payments)}\n"
        f"📝 Заметки: {student.get('notes', '—')}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=student_detail_keyboard(student_id),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("admin:student:") & F.data.endswith(":message"))
async def admin_message_student(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    student_id = int(callback.data.split(":")[2])
    await state.set_state(SendMessage.message)
    await state.update_data(student_id=student_id)
    await callback.message.edit_text(
        "✉️ Введите сообщение для ученика:"
    )


@router.message(SendMessage.message)
async def process_send_message(message: Message, state: FSMContext):
    data = await state.get_data()
    student_id = data["student_id"]
    try:
        await message.bot.send_message(
            student_id,
            f"📩 Сообщение от репетитора:\n\n{message.text}"
        )
        await message.answer("✅ Сообщение отправлено!")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")
    await state.clear()


@router.callback_query(F.data.startswith("admin:student:") & F.data.endswith(":deactivate"))
async def admin_deactivate_student(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    student_id = int(callback.data.split(":")[2])
    await db.update_student(student_id, is_active=0)
    await callback.answer("✅ Ученик деактивирован", show_alert=True)


@router.callback_query(F.data == "admin:students:reactivate")
async def admin_reactivate(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    inactive = await db.get_inactive_students(30)
    if not inactive:
        await callback.answer("Нет неактивных учеников", show_alert=True)
        return

    from utils.texts import Texts
    sent = 0
    errors = 0
    for student in inactive:
        try:
            await callback.bot.send_message(
                student["user_id"],
                Texts.REACTIVATION.format(name=student["full_name"])
            )
            sent += 1
        except Exception:
            errors += 1

    await callback.message.edit_text(
        f"📧 Рассылка неактивным завершена\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {errors}",
        reply_markup=back_button("admin:students")
    )


# =================== ПРЕДМЕТЫ ===================

@router.callback_query(F.data == "admin:subjects")
async def admin_subjects(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📚 **Управление предметами**",
        reply_markup=admin_subjects_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:subjects:list")
async def admin_subjects_list(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    subjects = await db.get_subjects()
    if not subjects:
        await callback.message.edit_text(
            "📭 Предметов пока нет.",
            reply_markup=back_button("admin:subjects")
        )
        return

    text = "📚 **Список предметов:**\n\n"
    for s in subjects:
        text += f"• **{s['name']}** — {s['price_per_hour']}₽/час\n"
        if s.get("description"):
            text += f"  _{s['description']}_\n"

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:subjects"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:subjects:add")
async def admin_add_subject(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(AddSubject.name)
    await callback.message.edit_text(
        "📚 Введите название предмета:"
    )


@router.message(AddSubject.name)
async def process_subject_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddSubject.price)
    await message.answer("💰 Введите цену за час (число):")


@router.message(AddSubject.price)
async def process_subject_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
    except ValueError:
        await message.answer("❌ Введите число. Попробуйте ещё раз:")
        return

    await state.update_data(price=price)
    await state.set_state(AddSubject.description)
    await message.answer(
        "📝 Введите описание (или отправьте '-' чтобы пропустить):"
    )


@router.message(AddSubject.description)
async def process_subject_description(message: Message, state: FSMContext):
    data = await state.get_data()
    description = "" if message.text == "-" else message.text
    subject_id = await db.add_subject(data["name"], data["price"], description)
    await state.clear()
    await message.answer(
        f"✅ Предмет «{data['name']}» добавлен!\n"
        f"💰 Цена: {data['price']}₽/час\n"
        f"🆔 ID: {subject_id}"
    )


# =================== РАСПИСАНИЕ ===================

@router.callback_query(F.data == "admin:schedule")
async def admin_schedule(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📅 **Управление расписанием**",
        reply_markup=admin_schedule_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:schedule:today")
async def admin_schedule_today(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    bookings = await db.get_today_bookings()
    from datetime import date
    today = date.today().isoformat()
    all_slots = await db.get_all_slots_for_date(today)

    text = f"📅 **Расписание на сегодня** ({format_date(today)})\n\n"

    if not all_slots and not bookings:
        text += "📭 Нет слотов на сегодня."
    else:
        for slot in all_slots:
            status = "🟢 Свободен" if slot["is_available"] else "🔴 Занят"
            text += f"🕐 {slot['start_time'][:5]}-{slot['end_time'][:5]} — {status}\n"

        if bookings:
            text += "\n📋 **Занятия:**\n"
            for b in bookings:
                text += (
                    f"  • {b['start_time'][:5]} — "
                    f"{b.get('full_name', '—')} "
                    f"({b.get('subject_name', '—')})\n"
                )

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:schedule"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:schedule:add_slot")
async def admin_add_slot(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(AddSlot.date)
    await callback.message.edit_text(
        "📅 Введите дату слота (ГГГГ-ММ-ДД):\n"
        "Например: 2025-01-15"
    )


@router.message(AddSlot.date)
async def process_slot_date(message: Message, state: FSMContext):
    try:
        from datetime import date as dt_date
        dt_date.fromisoformat(message.text)
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД:")
        return
    await state.update_data(date=message.text)
    await state.set_state(AddSlot.start_time)
    await message.answer("🕐 Введите время начала (ЧЧ:ММ):\nНапример: 14:00")


@router.message(AddSlot.start_time)
async def process_slot_start(message: Message, state: FSMContext):
    if ":" not in message.text or len(message.text) != 5:
        await message.answer("❌ Формат: ЧЧ:ММ. Попробуйте ещё раз:")
        return
    await state.update_data(start_time=message.text)
    await state.set_state(AddSlot.end_time)
    await message.answer("🕐 Введите время окончания (ЧЧ:ММ):")


@router.message(AddSlot.end_time)
async def process_slot_end(message: Message, state: FSMContext):
    if ":" not in message.text or len(message.text) != 5:
        await message.answer("❌ Формат: ЧЧ:ММ. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    slot_id = await db.add_time_slot(
        data["date"], data["start_time"], message.text
    )
    await state.clear()
    if slot_id:
        await message.answer(
            f"✅ Слот добавлен!\n\n"
            f"📅 {format_date(data['date'])}\n"
            f"🕐 {data['start_time']} — {message.text}"
        )
    else:
        await message.answer("⚠️ Слот на это время уже существует.")


# =================== ДОМАШНИЕ ЗАДАНИЯ (АДМИН) ===================

@router.callback_query(F.data == "admin:homework")
async def admin_homework(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📝 **Домашние задания**",
        reply_markup=admin_homework_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:hw:add")
async def admin_add_hw(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    students = await db.get_all_students()
    if not students:
        await callback.answer("Нет учеников", show_alert=True)
        return

    text = "👤 Выберите ученика (отправьте его ID):\n\n"
    for s in students:
        text += f"• {s['full_name']} — ID: `{s['user_id']}`\n"

    await state.set_state(AddHomework.student_id)
    await callback.message.edit_text(text, parse_mode="Markdown")


@router.message(AddHomework.student_id)
async def process_hw_student(message: Message, state: FSMContext):
    try:
        student_id = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число (ID ученика):")
        return

    student = await db.get_student(student_id)
    if not student:
        await message.answer("❌ Ученик не найден. Попробуйте другой ID:")
        return

    await state.update_data(student_id=student_id)
    await state.set_state(AddHomework.title)
    await message.answer(
        f"📝 Задание для {student['full_name']}\n\n"
        f"Введите название ДЗ:"
    )


@router.message(AddHomework.title)
async def process_hw_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddHomework.description)
    await message.answer("📄 Введите описание задания (или '-' для пропуска):")


@router.message(AddHomework.description)
async def process_hw_description(message: Message, state: FSMContext):
    desc = "" if message.text == "-" else message.text
    await state.update_data(description=desc)
    await state.set_state(AddHomework.due_date)
    await message.answer(
        "📅 Введите дату сдачи (ГГГГ-ММ-ДД) или '-' без дедлайна:"
    )


@router.message(AddHomework.due_date)
async def process_hw_due_date(message: Message, state: FSMContext):
    due_date = None if message.text == "-" else message.text
    data = await state.get_data()
    hw_id = await db.add_homework(
        data["student_id"], data["title"],
        data.get("description", ""), due_date=due_date
    )
    await state.clear()

    # Отправляем ученику уведомление
    try:
        from utils.texts import Texts
        subjects = await db.get_subjects()
        subject_name = "—"
        await message.bot.send_message(
            data["student_id"],
            Texts.HW_NEW.format(
                subject=subject_name,
                title=data["title"],
                description=data.get("description", ""),
                due_date=due_date or "Не указана"
            )
        )
    except Exception:
        pass

    await message.answer(f"✅ ДЗ #{hw_id} задано и отправлено ученику!")


@router.callback_query(F.data == "admin:hw:pending")
async def admin_hw_pending(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    # Показываем все ДЗ на проверке
    students = await db.get_all_students()
    text = "📝 **ДЗ на проверке:**\n\n"
    found = False

    for s in students:
        hw_list = await db.get_student_homework(s["user_id"], status="submitted")
        for hw in hw_list:
            found = True
            text += (
                f"• **{hw['title']}** — {s['full_name']}\n"
                f"  ID ДЗ: `{hw['id']}` | Сдано: {hw.get('submitted_at', '—')}\n\n"
            )

    if not found:
        text += "📭 Нет ДЗ на проверке."

    text += "\n\nДля проверки используйте кнопку ниже."

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Проверить ДЗ", callback_data="admin:hw:grade_start")
    builder.button(text="◀️ Назад", callback_data="admin:homework")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:hw:grade_start")
async def admin_grade_hw_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(GradeHomework.hw_id)
    await callback.message.edit_text("Введите ID домашнего задания для проверки:")


@router.message(GradeHomework.hw_id)
async def process_grade_hw_id(message: Message, state: FSMContext):
    try:
        hw_id = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число:")
        return
    await state.update_data(hw_id=hw_id)
    await state.set_state(GradeHomework.grade)
    await message.answer("📊 Введите оценку (например: 5, A, Отлично):")


@router.message(GradeHomework.grade)
async def process_grade(message: Message, state: FSMContext):
    await state.update_data(grade=message.text)
    await state.set_state(GradeHomework.feedback)
    await message.answer("💬 Введите комментарий (или '-' для пропуска):")


@router.message(GradeHomework.feedback)
async def process_feedback(message: Message, state: FSMContext):
    data = await state.get_data()
    feedback = "" if message.text == "-" else message.text
    await db.grade_homework(data["hw_id"], data["grade"], feedback)
    await state.clear()
    await message.answer(f"✅ ДЗ #{data['hw_id']} проверено!")


# =================== ОПЛАТЫ ===================

@router.callback_query(F.data == "admin:payments")
async def admin_payments(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "💳 **Управление оплатами**",
        reply_markup=admin_payments_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:pay:pending")
async def admin_pending_payments(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    payments = await db.get_pending_payments()
    if not payments:
        await callback.message.edit_text(
            "✅ Нет неоплаченных счетов.",
            reply_markup=back_button("admin:payments")
        )
        return

    text = "💳 **Ожидают оплаты:**\n\n"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    for p in payments:
        text += (
            f"• #{p['id']} — {p.get('full_name', '—')}: "
            f"{p['amount']}₽ ({p.get('description', '')})\n"
        )
        builder.button(
            text=f"✅ #{p['id']} Подтвердить",
            callback_data=f"admin:pay:confirm:{p['id']}"
        )

    builder.button(text="◀️ Назад", callback_data="admin:payments")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("admin:pay:confirm:"))
async def admin_confirm_payment(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    payment_id = int(callback.data.split(":")[-1])
    await db.confirm_payment(payment_id)
    await callback.answer("✅ Оплата подтверждена!", show_alert=True)
    # Обновляем список
    await admin_pending_payments(callback)


@router.callback_query(F.data == "admin:pay:create")
async def admin_create_payment(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    students = await db.get_all_students()
    text = "👤 Введите ID ученика для выставления счёта:\n\n"
    for s in students:
        text += f"• {s['full_name']} — ID: `{s['user_id']}`\n"

    await state.set_state(CreatePayment.student_id)
    await callback.message.edit_text(text, parse_mode="Markdown")


@router.message(CreatePayment.student_id)
async def process_payment_student(message: Message, state: FSMContext):
    try:
        student_id = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число:")
        return
    await state.update_data(student_id=student_id)
    await state.set_state(CreatePayment.amount)
    await message.answer("💰 Введите сумму:")


@router.message(CreatePayment.amount)
async def process_payment_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
    except ValueError:
        await message.answer("❌ Введите число:")
        return
    await state.update_data(amount=amount)
    await state.set_state(CreatePayment.description)
    await message.answer("📝 Введите описание (или '-'):")


@router.message(CreatePayment.description)
async def process_payment_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    desc = "" if message.text == "-" else message.text
    payment_id = await db.create_payment(
        data["student_id"], data["amount"], desc
    )
    await state.clear()

    # Уведомляем ученика
    try:
        from utils.texts import Texts
        await message.bot.send_message(
            data["student_id"],
            Texts.PAYMENT_REMINDER.format(
                amount=data["amount"],
                description=desc
            )
        )
    except Exception:
        pass

    await message.answer(f"✅ Счёт #{payment_id} создан и отправлен ученику!")


@router.callback_query(F.data == "admin:pay:stats")
async def admin_payment_stats(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    stats = await db.get_payment_stats(30)
    text = (
        "💰 **Финансовая статистика (30 дней)**\n\n"
        f"📊 Всего операций: {stats.get('total_payments', 0)}\n"
        f"✅ Оплачено: {stats.get('paid_count', 0)} "
        f"({stats.get('total_paid', 0):.0f}₽)\n"
        f"⏳ Ожидают: {stats.get('pending_count', 0)} "
        f"({stats.get('total_pending', 0):.0f}₽)\n"
    )
    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:payments"),
        parse_mode="Markdown"
    )


# =================== FAQ (АДМИН) ===================

@router.callback_query(F.data == "admin:faq")
async def admin_faq(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "❓ **Управление FAQ**",
        reply_markup=admin_faq_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:faq:list")
async def admin_faq_list(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    faqs = await db.get_all_faq()
    if not faqs:
        await callback.message.edit_text(
            "📭 FAQ пуст.",
            reply_markup=back_button("admin:faq")
        )
        return

    text = "❓ **Список FAQ:**\n\n"
    for faq in faqs:
        text += (
            f"**#{faq['id']}** {faq['question']}\n"
            f"_{faq['answer'][:50]}..._\n"
            f"Ключевые слова: {', '.join(faq.get('keywords', []))}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:faq"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:faq:add")
async def admin_add_faq(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(AddFAQ.question)
    await callback.message.edit_text("❓ Введите вопрос:")


@router.message(AddFAQ.question)
async def process_faq_question(message: Message, state: FSMContext):
    await state.update_data(question=message.text)
    await state.set_state(AddFAQ.answer)
    await message.answer("💬 Введите ответ:")


@router.message(AddFAQ.answer)
async def process_faq_answer(message: Message, state: FSMContext):
    await state.update_data(answer=message.text)
    await state.set_state(AddFAQ.keywords)
    await message.answer(
        "🔑 Введите ключевые слова через запятую "
        "(по ним бот будет находить этот ответ):\n\n"
        "Например: цена, стоимость, сколько стоит"
    )


@router.message(AddFAQ.keywords)
async def process_faq_keywords(message: Message, state: FSMContext):
    data = await state.get_data()
    keywords = [kw.strip() for kw in message.text.split(",")]
    faq_id = await db.add_faq(data["question"], data["answer"], keywords)
    await state.clear()
    await message.answer(f"✅ FAQ #{faq_id} добавлен!")


# =================== РАССЫЛКИ ===================

@router.callback_query(F.data == "admin:mailings")
async def admin_mailings(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📢 **Рассылки и реклама**",
        reply_markup=admin_mailings_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:mail:new")
async def admin_new_mailing(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(NewMailing.text)
    await callback.message.edit_text(
        "📢 Введите текст рассылки:\n\n"
        "Поддерживаются переменные:\n"
        "{name} — имя ученика"
    )


@router.message(NewMailing.text)
async def process_mailing_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(NewMailing.target)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Всем ученикам", callback_data="mail:target:students")
    builder.button(text="📢 В рекламные чаты", callback_data="mail:target:chats")
    builder.button(text="🔄 Неактивным", callback_data="mail:target:inactive")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)

    await message.answer(
        "🎯 Кому отправить?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("mail:target:"))
async def process_mailing_target(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":")[-1]
    await state.update_data(target=target)
    data = await state.get_data()

    await callback.message.edit_text(
        f"📢 **Подтверждение рассылки**\n\n"
        f"📝 Текст:\n{data['text']}\n\n"
        f"🎯 Цель: {target}\n\n"
        f"Отправить?",
        reply_markup=confirm_keyboard("mailing"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "confirm:mailing")
async def confirm_mailing(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    data = await state.get_data()
    target = data.get("target", "students")
    text = data.get("text", "")

    await callback.message.edit_text("⏳ Рассылка начата...")

    sent = 0
    errors = 0
    import asyncio

    if target == "students":
        students = await db.get_all_students()
        for s in students:
            try:
                personalized = text.replace("{name}", s["full_name"])
                await callback.bot.send_message(s["user_id"], personalized)
                sent += 1
                await asyncio.sleep(config.MAILING_DELAY_SECONDS)
            except Exception:
                errors += 1

    elif target == "chats":
        chats = await db.get_ad_chats()
        for chat in chats:
            try:
                await callback.bot.send_message(chat["chat_id"], text)
                sent += 1
                await asyncio.sleep(config.MAILING_DELAY_SECONDS)
            except Exception:
                errors += 1

    elif target == "inactive":
        inactive = await db.get_inactive_students(30)
        for s in inactive:
            try:
                personalized = text.replace("{name}", s["full_name"])
                await callback.bot.send_message(s["user_id"], personalized)
                sent += 1
                await asyncio.sleep(config.MAILING_DELAY_SECONDS)
            except Exception:
                errors += 1

    mailing_id = await db.create_mailing(text, target)
    await db.update_mailing_stats(mailing_id, sent, errors)

    await state.clear()
    await callback.message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {errors}",
        reply_markup=back_button("admin:mailings")
    )


@router.callback_query(F.data == "admin:mail:chats")
async def admin_ad_chats(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    chats = await db.get_ad_chats()
    if not chats:
        await callback.message.edit_text(
            "📭 Рекламных чатов нет.",
            reply_markup=back_button("admin:mailings")
        )
        return

    text = "📢 **Рекламные чаты:**\n\n"
    for c in chats:
        text += (
            f"• **{c.get('chat_title', '—')}**\n"
            f"  ID: `{c['chat_id']}` | Лидов: {c.get('total_leads', 0)}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:mailings"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:mail:add_chat")
async def admin_add_chat(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(AddAdChat.chat_id)
    await callback.message.edit_text(
        "📢 Введите ID чата для рекламы:\n\n"
        "Чтобы узнать ID, добавьте бота в чат и отправьте /chatid"
    )


@router.message(AddAdChat.chat_id)
async def process_chat_id(message: Message, state: FSMContext):
    try:
        chat_id = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число:")
        return
    await state.update_data(chat_id=chat_id)
    await state.set_state(AddAdChat.chat_title)
    await message.answer("📝 Введите название чата:")


@router.message(AddAdChat.chat_title)
async def process_chat_title(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_ad_chat(data["chat_id"], message.text)
    await state.clear()
    await message.answer(f"✅ Чат «{message.text}» добавлен!")


# =================== АНАЛИТИКА ===================

@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📊 **Аналитика**",
        reply_markup=admin_analytics_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:analytics:funnel")
async def admin_funnel(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    funnel = await db.get_funnel_stats(30)

    text = "📊 **Воронка продаж (30 дней)**\n\n"
    labels = {
        "ad_seen": "👁 Увидели рекламу",
        "bot_started": "▶️ Запустили бота",
        "trial_booked": "📅 Записались на пробное",
        "trial_attended": "✅ Пришли на пробное",
        "became_regular": "🎓 Стали постоянными",
    }

    prev_count = None
    for key, label in labels.items():
        count = funnel.get(key, 0)
        conversion = ""
        if prev_count and prev_count > 0:
            conv = round(count / prev_count * 100, 1)
            conversion = f" ({conv}%)"
        text += f"{label}: **{count}**{conversion}\n"
        prev_count = count

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:analytics"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:analytics:chats")
async def admin_chat_analytics(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    performance = await db.get_chat_performance()

    text = "📈 **Эффективность чатов**\n\n"
    if not performance:
        text += "📭 Данных пока нет."
    else:
        for p in performance:
            text += (
                f"📢 **{p.get('chat_title', '—')}**\n"
                f"  Лидов: {p.get('total_leads', 0)} | "
                f"Уникальных: {p.get('unique_users', 0)} | "
                f"Записей: {p.get('bookings', 0)}\n\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:analytics"),
        parse_mode="Markdown"
    )


# =================== DND ===================

@router.callback_query(F.data == "admin:dnd")
async def admin_dnd(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    is_active, _ = await db.is_dnd_active()
    status = "🔕 АКТИВЕН" if is_active else "🔔 Выключен"
    await callback.message.edit_text(
        f"🔕 **Режим «Не беспокоить»**\n\n"
        f"Статус: {status}",
        reply_markup=admin_dnd_menu(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:dnd:enable")
async def admin_dnd_enable(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(DndSetup.start_time)
    await callback.message.edit_text(
        "🕐 Введите время начала DND (ЧЧ:ММ):"
    )


@router.message(DndSetup.start_time)
async def process_dnd_start(message: Message, state: FSMContext):
    await state.update_data(start_time=message.text)
    await state.set_state(DndSetup.end_time)
    await message.answer("🕐 Введите время окончания DND (ЧЧ:ММ):")


@router.message(DndSetup.end_time)
async def process_dnd_end(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_dnd_schedule(data["start_time"], message.text)
    await state.clear()
    await message.answer(
        f"✅ DND установлен: {data['start_time']} — {message.text}"
    )


# =================== ОТЗЫВЫ (АДМИН) ===================

@router.callback_query(F.data == "admin:reviews")
async def admin_reviews(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    reviews = await db.get_reviews()
    avg = await db.get_average_rating()

    text = f"⭐ **Отзывы** (средний рейтинг: {avg})\n\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    if not reviews:
        text += "📭 Отзывов пока нет."
    else:
        for r in reviews[:10]:
            stars = "⭐" * r["rating"]
            pub = "✅" if r.get("is_published") else "❌"
            text += (
                f"{stars} — {r.get('full_name', '—')}\n"
                f"_{r.get('text', '—')}_\n"
                f"Опубликован: {pub}\n\n"
            )
            if not r.get("is_published"):
                builder.button(
                    text=f"📢 Опубликовать #{r['id']}",
                    callback_data=f"admin:review:publish:{r['id']}"
                )

    builder.button(text="◀️ Назад", callback_data="admin:back")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("admin:review:publish:"))
async def admin_publish_review(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    review_id = int(callback.data.split(":")[-1])
    await db.publish_review(review_id)
    await callback.answer("✅ Отзыв опубликован!", show_alert=True)


# =================== A/B ТЕСТЫ ===================

@router.callback_query(F.data == "admin:ab_tests")
async def admin_ab_tests(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    tests = await db.get_active_ab_tests()

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    text = "🧪 **A/B Тесты**\n\n"
    if not tests:
        text += "📭 Нет активных тестов."
    else:
        for t in tests:
            a_ctr = (
                round(t["variant_a_clicks"] / t["variant_a_sends"] * 100, 1)
                if t["variant_a_sends"] > 0 else 0
            )
            b_ctr = (
                round(t["variant_b_clicks"] / t["variant_b_sends"] * 100, 1)
                if t["variant_b_sends"] > 0 else 0
            )
            winner = "A" if a_ctr >= b_ctr else "B"
            text += (
                f"**{t['name']}**\n"
                f"  A: {t['variant_a_sends']} отправок, "
                f"CTR {a_ctr}%\n"
                f"  B: {t['variant_b_sends']} отправок, "
                f"CTR {b_ctr}%\n"
                f"  🏆 Лидер: Вариант {winner}\n\n"
            )

    builder.button(text="➕ Новый тест", callback_data="admin:ab:new")
    builder.button(text="◀️ Назад", callback_data="admin:back")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:ab:new")
async def admin_new_ab(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(ABTestSetup.name)
    await callback.message.edit_text("🧪 Введите название теста:")


@router.message(ABTestSetup.name)
async def process_ab_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ABTestSetup.variant_a)
    await message.answer("📝 Введите текст варианта A:")


@router.message(ABTestSetup.variant_a)
async def process_ab_a(message: Message, state: FSMContext):
    await state.update_data(variant_a=message.text)
    await state.set_state(ABTestSetup.variant_b)
    await message.answer("📝 Введите текст варианта B:")


@router.message(ABTestSetup.variant_b)
async def process_ab_b(message: Message, state: FSMContext):
    data = await state.get_data()
    test_id = await db.create_ab_test(
        data["name"], data["variant_a"], message.text
    )
    await state.clear()
    await message.answer(f"✅ A/B тест #{test_id} создан!")


# =================== РЕФЕРАЛЬНАЯ СИСТЕМА ===================

@router.callback_query(F.data == "admin:referrals")
async def admin_referrals(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    students = await db.get_all_students()
    text = "🎯 **Реферальная система**\n\n"

    total_refs = 0
    for s in students:
        stats = await db.get_referral_stats(s["user_id"])
        if stats["total_referrals"] > 0:
            total_refs += stats["total_referrals"]
            text += (
                f"• {s['full_name']}: "
                f"{stats['total_referrals']} приглашено, "
                f"{stats['completed']} активировано\n"
            )

    if total_refs == 0:
        text += "📭 Рефералов пока нет."

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:back"),
        parse_mode="Markdown"
    )


# =================== НАСТРОЙКИ ===================

@router.callback_query(F.data == "admin:settings")
async def admin_settings(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    text = (
        "⚙️ **Настройки**\n\n"
        f"🔑 Admin IDs: {config.ADMIN_IDS}\n"
        f"⏱ Время DND: {config.DND_START} — {config.DND_END}\n"
        f"🎁 Реферальный бонус: {config.REFERRAL_BONUS_PERCENT}%\n"
        f"⏳ Задержка рассылки: {config.MAILING_DELAY_SECONDS}с\n"
        f"📊 Макс. рассылок/день: {config.MAX_MAILING_PER_DAY}\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:back"),
        parse_mode="Markdown"
    )


# =================== УВЕДОМЛЕНИЯ ===================

@router.callback_query(F.data == "admin:notifications")
async def admin_notifications(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📊 Утренняя сводка сейчас",
        callback_data="admin:notif:morning"
    )
    builder.button(text="◀️ Назад", callback_data="admin:back")
    builder.adjust(1)

    await callback.message.edit_text(
        "🔔 **Уведомления**\n\n"
        "Утренняя сводка отправляется ежедневно в 8:00.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:notif:morning")
async def send_morning_now(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    from services.notification import send_morning_summary
    await send_morning_summary(callback.bot)
    await callback.answer("✅ Утренняя сводка отправлена!", show_alert=True)


# =================== ОТМЕНА ===================

@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id in config.ADMIN_IDS:
        if await db.check_admin_session(callback.from_user.id):
            stats = await db.get_dashboard_stats()
            text = Texts.ADMIN_PANEL.format(**stats)
            await callback.message.edit_text(
                text, reply_markup=admin_main_menu(),
                parse_mode="Markdown"
            )
            return
    await callback.message.edit_text("❌ Действие отменено.")
from services.userbot import userbot
from aiogram.utils.keyboard import InlineKeyboardBuilder
import random


# =================== USERBOT РАССЫЛКА ===================

@router.callback_query(F.data == "admin:mail:userbot")
async def admin_userbot_start(callback: CallbackQuery, state: FSMContext):
    """Начало авторизации личного аккаунта"""
    if not await check_admin(callback):
        return
    
    # Проверяем, уже авторизован ли аккаунт
    if userbot.is_connected:
        await callback.message.edit_text(
            "✅ Твой личный аккаунт уже подключен!\n\n"
            "Выбери действие:",
            reply_markup=get_userbot_menu()
        )
        return
    
    await state.set_state(UserbotLogin.phone)
    await callback.message.edit_text(
        "📱 Введи номер телефона аккаунта репетитора:\n\n"
        "⚠️ Формат: +79991234567\n\n"
        "На этот номер придет код подтверждения Telegram."
    )


@router.message(UserbotLogin.phone)
async def process_userbot_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("❌ Номер должен начинаться с + (например +79991234567):")
        return
    
    # Подключаем клиента если не подключен
    if not userbot.client:
        await userbot.connect()
    
    # Отправляем код запрос
    success = await userbot.send_code_request(phone)
    if success:
        await state.update_data(phone=phone)
        await state.set_state(UserbotLogin.code)
        await message.answer(
            "📩 Telegram отправил код на этот номер.\n\n"
            "Введи код (цифры через пробел или слитно):\n\n"
            "Например: 1 2 3 4 5 или 12345"
        )
    else:
        await message.answer("❌ Ошибка отправки кода. Проверь номер и попробуй снова.")


@router.message(UserbotLogin.code)
async def process_userbot_code(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = data["phone"]
    code = message.text.strip()
    
    success = await userbot.sign_in(phone, code)
    if success:
        await state.clear()
        me = await userbot.client.get_me()
        await message.answer(
            f"✅ Аккаунт подключен!\n\n"
            f"👤 Имя: {me.first_name}\n"
            f"📱 Номер: {phone}\n\n"
            f"Теперь ты можешь делать рассылку от своего имени.",
            reply_markup=get_userbot_menu()
        )
    else:
        await message.answer("❌ Неверный код. Попробуй ещё раз:")


def get_userbot_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Новая рассылка", callback_data="admin:ub:mailing")
    builder.button(text="📋 Мои чаты", callback_data="admin:ub:chats")
    builder.button(text="📊 Активные рассылки", callback_data="admin:ub:active")
    builder.button(text="🔓 Отключить аккаунт", callback_data="admin:ub:disconnect")
    builder.button(text="◀️ Назад", callback_data="admin:mailings")
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(F.data == "admin:ub:mailing")
async def admin_ub_mailing(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    
    if not userbot.is_connected:
        await callback.answer("❌ Сначала подключи аккаунт!", show_alert=True)
        return
    
    # Получаем список чатов
    chats = await userbot.get_chats(limit=20)
    if not chats:
        await callback.message.edit_text(
            "📭 Не найдено групп и каналов.",
            reply_markup=back_button("admin:mailings")
        )
        return
    
    # Сохраняем чаты в state
    await state.update_data(chats=chats)
    
    builder = InlineKeyboardBuilder()
    for chat in chats:
        title = chat["title"][:30]
        builder.button(
            text=f"💬 {title} ({chat['type']})",
            callback_data=f"ub:chat:{chat['id']}"
        )
    builder.button(text="◀️ Назад", callback_data="admin:mailings")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "💬 Выбери чат для рассылки:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("ub:chat:"))
async def admin_ub_select_chat(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    
    chat_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    chats = data.get("chats", [])
    chat_name = next(
        (c["title"] for c in chats if c["id"] == chat_id), "Неизвестно"
    )
    
    await state.update_data(target_chat_id=chat_id, target_chat_name=chat_name)
    await state.set_state(UserbotMailing.text)
    
    await callback.message.edit_text(
        f"💬 Чат: **{chat_name}**\n\n"
        f"📝 Введи текст сообщения для рассылки:\n\n"
        f"⚠️ Советы против бана:\n"
        f"• Не отправляй одно и то же каждый раз\n"
        f"• Добавляй эмодзи или меняй слова\n"
        f"• Не делай текст слишком длинным",
        parse_mode="Markdown"
    )


@router.message(UserbotMailing.text)
async def process_ub_mailing_text(message: Message, state: FSMContext):
    await state.update_data(mailing_text=message.text)
    await state.set_state(UserbotMailing.schedule_type)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⏰ Каждый день в определённое время", callback_data="ub:sched:daily")
    builder.button(text="🔄 Каждый N часов", callback_data="ub:sched:hours")
    builder.button(text="▶️ Один раз сейчас", callback_data="ub:sched:now")
    builder.button(text="❌ Отмена", callback_data="cancel") # Исправлено button9
    builder.adjust(1)
    
    await message.answer(
        "📅 Выбери тип расписания:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("ub:sched:"))
async def admin_ub_schedule(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    
    sched_type = callback.data.split(":")[-1]
    data = await state.get_data()
    
    if sched_type == "now":
        # Отправить прямо сейчас (с безопасной задержкой)
        chat_id = data["target_chat_id"]
        text = data["mailing_text"]
        
        await callback.message.edit_text("⏳ Отправка сообщения...")
        
        success = await userbot.send_message_safe(chat_id, text)
        
        if success:
            await callback.message.edit_text(
                "✅ Сообщение отправлено!\n\n"
                "⏱ Была добавлена случайная задержка для безопасности.",
                reply_markup=back_button("admin:mailings")
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка отправки. Возможно, нет прав писать в этот чат.",
                reply_markup=back_button("admin:mailings")
            )
        await state.clear()
        return
    
    elif sched_type == "daily":
        await state.update_data(schedule_type="daily") # Сохраняем тип
        await state.set_state(UserbotMailing.schedule_time) # Исправлено
        await callback.message.edit_text(
            "⏰ Введи время отправки (по Мск) в формате ЧЧ:ММ:\n\n"
            "Например: 10:00\n\n"
            "⚠️ Бот добавит случайные 1-15 минут к этому времени\n"
            "для безопасности от бана."
        )
    
    elif sched_type == "hours":
        await state.update_data(schedule_type="hours") # Сохраняем тип
        await state.set_state(UserbotMailing.schedule_time) # Исправлено
        await callback.message.edit_text(
            "🔄 Введи интервал в часах:\n\n"
            "Например: 4 (каждые 4 часа)\n\n"
            "⚠️ Минимум 2 часа для безопасности!"
        )

@router.message(UserbotMailing.schedule_time)
async def process_ub_schedule_time(message: Message, state: FSMContext):
    data = await state.get_data()
    sched_type = data.get("schedule_type", "daily")
    
    if sched_type == "hours":
        try:
            hours = float(message.text)
            if hours < 2:
                await message.answer("❌ Минимум 2 часа! Введи ещё раз:")
                return
        except ValueError:
            await message.answer("❌ Введи число (например 4):")
            return
        
        # Создаём периодическую задачу
        chat_id = data["target_chat_id"]
        chat_name = data["target_chat_name"]
        text = data["mailing_text"]
        
        from services.scheduler import bot_scheduler
        job_id = f"ub_mail_{chat_id}_{random.randint(1000,9999)}"
        
        bot_scheduler.scheduler.add_job(
            userbot.send_message_safe,
            trigger="interval",
            hours=hours,
            args=[chat_id, text],
            id=job_id,
            replace_existing=True,
            jitter=900  # случайный разброс до 15 минут
        )
        
        await state.clear()
        await message.answer(
            f"✅ Рассылка настроена!\n\n"
            f"💬 Чат: {chat_name}\n"
            f"🔄 Каждые {hours} часов\n"
            f"📝 Текст: {text[:50]}...\n\n"
            f"🛡 Добавлен случайный разброс до 15 минут."
        )
    
    else:  # daily
        time_str = message.text.strip()
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError
        except (ValueError, IndexError):
            await message.answer("❌ Формат ЧЧ:ММ. Например 10:00:")
            return
        
        chat_id = data["target_chat_id"]
        chat_name = data["target_chat_name"]
        text = data["mailing_text"]
        
        from services.scheduler import bot_scheduler
        job_id = f"ub_mail_{chat_id}_{random.randint(1000,9999)}"
        
        bot_scheduler.scheduler.add_job(
            userbot.send_message_safe,
            trigger="cron",
            hour=hour,
            minute=minute,
            args=[chat_id, text],
            id=job_id,
            replace_existing=True,
            jitter=900  # случайный разброс до 15 минут
        )
        
        await state.clear()
        await message.answer(
            f"✅ Рассылка настроена!\n\n"
            f"💬 Чат: {chat_name}\n"
            f"⏰ Каждый день в {time_str} (Мск)\n"
            f"📝 Текст: {text[:50]}...\n\n"
            f"🛡 Добавлен случайный разброс 1-15 минут."
        )


@router.callback_query(F.data == "admin:ub:chats")
async def admin_ub_chats(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    chats = await userbot.get_chats()
    text = "💬 **Твои чаты:**\n\n"
    for c in chats:
        text += f"• {c['title']} ({c['type']}) — ID: `{c['id']}`\n"
    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:mail:userbot"),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:ub:disconnect")
async def admin_ub_disconnect(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await userbot.disconnect()
    await callback.message.edit_text(
        "🔓 Аккаунт отключен. Сессия сохранена — в следующий раз "
        "код не потребуется.",
        reply_markup=back_button("admin:mailings")
    )