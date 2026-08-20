from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from config import config
from keyboards.admin_kb import back_button
from utils.helpers import escape_html, truncate_text
import asyncio
import logging
logger = logging.getLogger(__name__)
router = Router()
class NewMailingFlow(StatesGroup):
    text = State()
    target = State()
    delay = State()
    confirm = State()
# =================== СОЗДАТЬ РАССЫЛКУ ===================
@router.callback_query(F.data == "admin:mail:new")
async def start_mailing(callback: CallbackQuery, state: FSMContext):
    await state.set_state(NewMailingFlow.text)
    await callback.message.edit_text("📢 Введите текст рассылки (макс 4096 символов):")
@router.message(NewMailingFlow.text)
async def mailing_text(message: Message, state: FSMContext):
    text = message.text
    if not text or len(text) > 4096:
        await message.answer("❌ Текст от 1 до 4096 символов:")
        return
    await state.update_data(text=text)
    await state.set_state(NewMailingFlow.target)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Все ученики", callback_data="mail:target:all")
    builder.button(text="💤 Неактивные", callback_data="mail:target:inactive")
    builder.button(text="❌ Отмена", callback_data="mail:cancel")
    builder.adjust(1)
    await message.answer("Кому отправить?", reply_markup=builder.as_markup())
@router.callback_query(F.data.startswith("mail:target:"))
async def mailing_target(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":")[-1]
    if target not in ("all", "inactive"):
        await callback.answer("Неизвестный тип", show_alert=True)
        return
    data = await state.get_data()
    mailing_text = data.get("text", "")
    await state.update_data(target=target)
    await state.set_state(NewMailingFlow.delay)
    target_label = "Все ученики" if target == "all" else "Неактивные"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for sec in ("0", "1", "3", "5", "10"):
        builder.button(text=f"⏱ {sec} сек", callback_data=f"mail:delay:{sec}")
    builder.button(text="❌ Отмена", callback_data="mail:cancel")
    builder.adjust(3)
    await callback.message.edit_text(
        f"📢 <b>Рассылка</b>\n\n"
        f"📝 Текст:\n{escape_html(mailing_text[:300])}\n\n"
        f"👥 Цель: {target_label}\n\n"
        f"Выберите задержку между сообщениями:",
        reply_markup=builder.as_markup()
    )
@router.callback_query(F.data.startswith("mail:delay:"))
async def mailing_delay(callback: CallbackQuery, state: FSMContext):
    delay = int(callback.data.split(":")[-1])
    await state.update_data(delay=delay)
    await state.set_state(NewMailingFlow.confirm)
    data = await state.get_data()
    target_label = "Все ученики" if data.get("target") == "all" else "Неактивные"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="mail:confirm:yes")
    builder.button(text="❌ Отмена", callback_data="mail:cancel")
    builder.adjust(2)
    await callback.message.edit_text(
        f"📢 <b>Предпросмотр рассылки</b>\n\n"
        f"📝 Текст:\n{escape_html(data.get('text', '')[:500])}\n\n"
        f"👥 Цель: {target_label}\n"
        f"⏱ Задержка: {delay} сек\n\n"
        f"Подтвердите отправку:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "mail:confirm:yes")
async def mailing_confirm(callback: CallbackQuery, state: FSMContext):
    """Отправка рассылки (без дневного лимита)."""
    data = await state.get_data()
    text = data.get("text", "")
    target = data.get("target", "all")
    delay = data.get("delay", 3)
    await state.clear()
    # Получаем список учеников
    all_students = await db.get_all_students()
    if target == "inactive":
        students_list = [s for s in all_students if not s.get("is_active", True)]
    else:
        students_list = all_students
    if not students_list:
        await callback.message.edit_text("📭 Нет учеников для рассылки.")
        return
    # Создаём запись в БД
    try:
        cursor = await db.db.execute(
            """INSERT INTO mailings (text, target_type, status, total_sent, total_errors)
               VALUES (?, ?, 'sending', 0, 0)""",
            (text, target)
        )
        await db.db.commit()
        mailing_id = cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to create mailing record: {e}")
        await callback.message.edit_text("❌ Ошибка при создании рассылки.")
        return
    await callback.message.edit_text("📤 Рассылка отправляется...")
    sent = 0
    errors = 0
    for student in students_list:
        try:
            await callback.bot.send_message(student["user_id"], text)
            sent += 1
            await asyncio.sleep(delay)
        except Exception as e:
            logger.warning(f"Mailing failed for {student['user_id']}: {e}")
            errors += 1
    # Обновляем статус
    try:
        await db.db.execute(
            """UPDATE mailings 
               SET status = 'sent', sent_at = datetime('now'),
                   total_sent = ?, total_errors = ?
               WHERE id = ?""",
            (sent, errors, mailing_id)
        )
        await db.db.commit()
    except Exception as e:
        logger.error(f"Failed to update mailing status: {e}")
    await callback.message.edit_text(
        f"✅ Рассылка отправлена!\n\n"
        f"📤 Доставлено: {sent}\n"
        f"❌ Ошибок:' {errors}"
    )
@router.callback_query(F.data == "mail:cancel")
async def cancel_mailing(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена.")
# =================== СПИСОК РАССЫЛОК ===================
@router.callback_query(F.data == "admin:mail:stats")
async def mailing_stats(callback: CallbackQuery):
    try:
        cursor = await db.db.execute(
            "SELECT * FROM mailings ORDER BY created_at DESC LIMIT 10"
        )
        rows = await cursor.fetchall()
        mailings_list = [dict(r) for r in rows]
        if not mailings_list:
            await callback.message.edit_text(
                "📭 Рассылок нет.",
                reply_markup=back_button("admin:mailings"),
            )
            return
        text = "📢 <b>Последние рассылки:</b>\n\n"
        for m in mailings_list:
            status_emoji = {"draft": "📝", "sending": "📤", "sent": "✅", "failed": "❌"}
            text += (
                f"{status_emoji.get(m['status'], '❔')} "
                f"{escape_html(truncate_text(m['text'], 40))} — "
                f"✉️{m['total_sent']} ❌{m['total_errors']}\n"
            )
        await callback.message.edit_text(
            text,
            reply_markup=back_button("admin:mailings"),
        )
    except Exception as e:
        logger.error(f"Mailing stats error: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== РЕКЛАМНЫЕ ЧАТЫ ===================
@router.callback_query(F.data == "admin:mail:chats")
async def ad_chats_list(callback: CallbackQuery):
    try:
        cursor = await db.db.execute(
            "SELECT * FROM ad_chats WHERE is_active = 1 ORDER BY added_at DESC"
        )
        rows = await cursor.fetchall()
        chats = [dict(r) for r in rows]
        if not chats:
            await callback.message.edit_text(
                "📭 Рекламных чатов нет.",
                reply_markup=back_button("admin:mailings"),
            )
            return
        text = "📢 <b>Рекламные чаты:</b>\n\n"
        for c in chats:
            text += (
                f"💬 {escape_html(c['chat_title'])} — "
                f"{c['total_leads']} лидов\n"
            )
        await callback.message.edit_text(
            text,
            reply_markup=back_button("admin:mailings"),
        )
    except Exception as e:
        logger.error(f"Ad chats list error: {e}")
        await callback.answer("Ошибка", show_alert=True)