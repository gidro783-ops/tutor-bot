from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards.student_kb import homework_list_keyboard
from utils.helpers import escape_html
from config import config
import logging
logger = logging.getLogger(__name__)
router = Router()
class SubmitHomework(StatesGroup):
    file_or_text = State()
class AddHomeworkAdmin(StatesGroup):
    student_id = State()
    subject_id = State()
    title = State()
    description = State()
    due_date = State()
class GradeHomeworkAdmin(StatesGroup):
    hw_id = State()
    grade = State()
    feedback = State()
# =================== УЧЕНИК: список ДЗ ===================
@router.message(F.text == "📝 Домашние задания")
async def my_homework_menu(message: Message):
    hw_list = await db.get_student_homework(message.from_user.id)
    if not hw_list:
        await message.answer("📭 Домашних заданий пока нет.")
        return
    await message.answer(
        "📝 <b>Ваши задания:</b>",
        reply_markup=homework_list_keyboard(hw_list),
    )
@router.callback_query(F.data.startswith("hw:view:"))
async def view_homework(callback: CallbackQuery):
    hw_id = int(callback.data.split(":")[-1])
    hw = await db.get_homework_by_id(hw_id)
    if not hw:
        await callback.answer("Не найдено", show_alert=True)
        return
    status_emoji = {"assigned": "📝", "submitted": "📤", "graded": "✅"}
    text = (
        f"📌 <b>{escape_html(hw['title'])}</b>\n\n"
        f"📝 Статус: {status_emoji.get(hw['status'], '❔')} {hw['status']}\n"
        f"📋 Описание: {escape_html(hw.get('description', '—'))}\n"
    )
    if hw.get("due_date"):
        text += f"📅 Сдать до: {hw['due_date'][:10]}\n"
    if hw.get("grade"):
        text += f"\n✅ Оценка: {escape_html(hw['grade'])}\n💬 {escape_html(hw.get('feedback', ''))}"
    from keyboards.student_kb import hw_detail_keyboard
    await callback.message.edit_text(
        text,
        reply_markup=hw_detail_keyboard(hw_id, hw["status"]),
    )
# =================== УЧЕНИК: сдать ДЗ ===================
@router.callback_query(F.data.startswith("hw:submit:"))
async def submit_homework(callback: CallbackQuery, state: FSMContext):
    hw_id = int(callback.data.split(":")[-1])
    await state.update_data(hw_id=hw_id)
    await state.set_state(SubmitHomework.file_or_text)
    await callback.message.edit_text(
        "📤 Отправьте текст ответа или файл с решением:"
    )
@router.message(SubmitHomework.file_or_text)
async def process_homework_submit(message: Message, state: FSMContext):
    data = await state.get_data()
    hw_id = data.get("hw_id")
    try:
        submitted_text = message.text or "(файл/фото)"
        # Обновляем статус ДЗ на "submitted"
        cursor = await db.db.execute(
            """UPDATE homework 
               SET status = 'submitted', submitted_at = datetime('now'), 
                   description = description || '\n\n📤 Ответ: ' || ?
               WHERE id = ? AND status = 'assigned'""",
            (submitted_text[:2000], hw_id)
        )
        await db.db.commit()
        if cursor.rowcount == 0:
            await state.clear()
            await message.answer("❌ ДЗ уже сдано или не найдено.")
            return
        await state.clear()
        await message.answer("✅ Домашнее задание сдано! Репетитор проверит его.")
        # Уведомляем админа
        for admin_id in config.ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"📤 Ученик сдал ДЗ #{hw_id}\n"
                    f"📝 Ответ: {escape_html(submitted_text[:100])}"
                )
            except Exception as e:
                logger.warning(f"Failed to notify admin about HW submit: {e}")
    except Exception as e:
        logger.error(f"Failed to submit homework {hw_id}: {e}")
        await message.answer("❌ Ошибка при сдаче ДЗ. Попробуйте позже.")
        await state.clear()
# =================== АДМИН: задать ДЗ ===================
@router.callback_query(F.data == "admin:hw:add")
async def admin_add_hw_start(callback: CallbackQuery, state: FSMContext):
    students_list = await db.get_all_students()
    if not students_list:
        await callback.answer("Нет учеников", show_alert=True)
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for s in students_list[:20]:
        builder.button(
            text=f"👤 {s['full_name'][:30]}",
            callback_data=f"admin:hw:to:{s['user_id']}"
        )
    builder.button(text="◀️ Назад", callback_data="admin:homework")
    builder.adjust(1)
    await callback.message.edit_text(
        "👤 Выберите ученика:",
        reply_markup=builder.as_markup()
    )
@router.callback_query(F.data.startswith("admin:hw:to:"))
async def admin_hw_select_student(callback: CallbackQuery, state: FSMContext):
    student_id = int(callback.data.split(":")[-1])
    await state.update_data(student_id=student_id)
    await state.set_state(AddHomeworkAdmin.title)
    await callback.message.edit_text("📌 Введите название задания:")
@router.message(AddHomeworkAdmin.title)
async def admin_hw_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title or len(title) > 500:
        await message.answer("❌ Название от 1 до 500 символов:")
        return
    await state.update_data(title=title)
    await state.set_state(AddHomeworkAdmin.description)
    await message.answer("📋 Введите описание (или «-» чтобы пропустить):")
@router.message(AddHomeworkAdmin.description)
async def admin_hw_description(message: Message, state: FSMContext):
    desc = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddHomeworkAdmin.due_date)
    await message.answer("📅 Введите дедлайн YYYY-MM-DD (или «-» без дедлайна):")
@router.message(AddHomeworkAdmin.due_date)
async def admin_hw_due_date(message: Message, state: FSMContext):
    from utils.helpers import validate_date
    due = None
    text = message.text.strip()
    if text != "-":
        try:
            due = validate_date(text)
        except ValueError as e:
            await message.answer(f"❌ {e}\n\nВведите дату ещё раз:")
            return
    data = await state.get_data()
    try:
        await db.db.execute(
            """INSERT INTO homework (student_id, title, description, due_date, status)
               VALUES (?, ?, ?, ?, 'assigned')""",
            (data["student_id"], data["title"], data["description"], due)
        )
        await db.db.commit()
        await state.clear()
        # Уведомляем ученика
        try:
            await message.bot.send_message(
                data["student_id"],
                f"📝 <b>Новое домашнее задание!</b>\n\n"
                f"📌 {escape_html(data['title'])}\n"
                f"📋 {escape_html(data['description'])}\n"
                + (f"📅 Сдать до: {due}" if due else "")
            )
        except Exception as e:
            logger.warning(f"Failed to notify student about new HW: {e}")
        await message.answer(f"✅ ДЗ <b>{escape_html(data['title'])}</b> задано!")
    except Exception as e:
        logger.error(f"Failed to create homework: {e}")
        await state.clear()
        await message.answer("❌ Ошибка при создании ДЗ.")
# =================== АДМИН: оценить ДЗ ===================
@router.callback_query(F.data.startswith("admin:hw:grade:"))
async def admin_grade_hw_start(callback: CallbackQuery, state: FSMContext):
    hw_id = int(callback.data.split(":")[-1])
    await state.update_data(hw_id=hw_id)
    await state.set_state(GradeHomeworkAdmin.grade)
    await callback.message.edit_text("📊 Введите оценку (например «5/5» или «Отлично»):")
@router.message(GradeHomeworkAdmin.grade)
async def admin_grade_hw_grade(message: Message, state: FSMContext):
    grade = message.text.strip()
    if not grade or len(grade) > 50:
        await message.answer("❌ Оценка от 1 до 50 символов:")
        return
    await state.update_data(grade=grade)
    await state.set_state(GradeHomeworkAdmin.feedback)
    await message.answer("💬 Введите комментарий (или «-» без комментария):")
@router.message(GradeHomeworkAdmin.feedback)
async def admin_grade_hw_feedback(message: Message, state: FSMContext):
    feedback = "" if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    try:
        cursor = await db.db.execute(
            """UPDATE homework 
               SET status = 'graded', grade = ?, feedback = ?
               WHERE id = ?""",
            (data["grade"], feedback, data["hw_id"])
        )
        await db.db.commit()
        if cursor.rowcount == 0:
            await state.clear()
            await message.answer("❌ ДЗ не найдено.")
            return
        await state.clear()
        await message.answer(f"✅ ДЗ оценено: {escape_html(data['grade'])}")
        # Уведомляем ученика
        hw = await db.get_homework_by_id(data["hw_id"])
        if hw:
            try:
                await message.bot.send_message(
                    hw["student_id"],
                    f"✅ <b>Ваше ДЗ проверено!</b>\n\n"
                    f"📌 {escape_html(hw['title'])}\n"
                    f"📊 Оценка: {escape_html(data['grade'])}\n"
                    + (f"💬 {escape_html(feedback)}" if feedback else "")
                )
            except Exception as e:
                logger.warning(f"Failed to notify student about graded HW: {e}")
    except Exception as e:
        logger.error(f"Failed to grade homework: {e}")
        await state.clear()
        await message.answer("❌ Ошибка при оценке ДЗ.")
# =================== НАВИГАЦИЯ ===================
@router.callback_query(F.data == "hw:list")
async def hw_list(callback: CallbackQuery):
    hw_list = await db.get_student_homework(callback.from_user.id)
    if not hw_list:
        await callback.message.edit_text("📭 Домашних заданий нет.")
        return
    await callback.message.edit_text(
        "📝 <b>Ваши задания:</b>",
        reply_markup=homework_list_keyboard(hw_list),
    )