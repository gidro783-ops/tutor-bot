# -*- coding: utf-8 -*-
"""Админка: подменю «Ещё» — шаблоны быстрых ответов, отложенные
сообщения, материалы, плюс ссылки на редко используемые разделы."""
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import db
from keyboards.subscription_kb import cancel_flow_kb
from utils.helpers import escape_html

from .core import check_admin

logger = logging.getLogger(__name__)
router = Router()


class TplStates(StatesGroup):
    title = State()
    text = State()
    send_to = State()  # выбранный шаблон → выбор ученика


class DelayStates(StatesGroup):
    student = State()
    text = State()
    when = State()


class MatStates(StatesGroup):
    title = State()
    file = State()


def _back_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ В меню", callback_data="admin:back")
    return builder.as_markup()


# =================== ПОДМЕНЮ «ЕЩЁ» ===================
@router.callback_query(F.data == "admin:more")
async def admin_more(callback: CallbackQuery, state: FSMContext | None = None):
    if not await check_admin(callback):
        return
    if state:
        await state.clear()
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📤 Шаблоны ответов", "admin:tpl"),
        ("⏰ Отложенные сообщения", "admin:delayed"),
        ("📂 Материалы", "admin:mat"),
        ("🔔 Уведомления", "admin:notifications"),
        ("🔕 Режим DND", "admin:dnd"),
        ("🎯 Реферальная система", "admin:referrals"),
        ("🧪 A/B тесты", "admin:ab_tests"),
        ("📚 Предметы", "admin:subjects"),
        ("⭐ Отзывы", "admin:reviews"),
        ("⚙️ Настройки", "admin:settings"),
        ("◀️ В меню", "admin:back"),
    ]
    for text, data in buttons:
        builder.button(text=text, callback_data=data)
    builder.adjust(2, 2, 2, 2, 2, 1)
    await callback.message.edit_text("⚙️ <b>Ещё</b>", reply_markup=builder.as_markup())


# =================== ШАБЛОНЫ ===================
@router.callback_query(F.data == "admin:tpl")
async def tpl_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.clear()
    await _show_templates(callback)


async def _show_templates(callback: CallbackQuery):
    items = await db.get_templates()
    builder = InlineKeyboardBuilder()
    text = "📤 <b>Шаблоны быстрых ответов</b>\n\n"
    if not items:
        text += "Пока пусто. Создайте первый — отправлять ученикам в 1 клик."
    for t in items[:10]:
        text += f"• <b>{escape_html(t['title'])}</b>\n"
        builder.button(text=f"📤 {t['title'][:25]}", callback_data=f"tpl:send:{t['id']}")
        builder.button(text="🗑", callback_data=f"tpl:del:{t['id']}")
    builder.button(text="➕ Создать шаблон", callback_data="admin:tpl:add")
    builder.button(text="◀️ Ещё", callback_data="admin:more")
    builder.adjust(2, 2, 2, 2, 2, 2, 1, 1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "admin:tpl:add")
async def tpl_add(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(TplStates.title)
    await callback.message.edit_text(
        "📤 Название шаблона (например «Напоминание об оплате»):",
        reply_markup=cancel_flow_kb(),
    )


@router.message(TplStates.title)
async def tpl_title(message: Message, state: FSMContext):
    from services.cleanup import say
    from utils.helpers import is_cancel

    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Создание шаблона отменено.")
        return
    title = (message.text or "").strip()[:100]
    if not title:
        await say(message, "❌ Название не может быть пустым:")
        return
    await state.update_data(title=title)
    await state.set_state(TplStates.text)
    await say(message, "📝 Текст шаблона (можно с подстановкой {name} — имя ученика):")


@router.message(TplStates.text)
async def tpl_text(message: Message, state: FSMContext):
    from services.cleanup import say
    from utils.helpers import is_cancel

    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Создание шаблона отменено.")
        return
    body = (message.text or "").strip()[:3000]
    data = await state.get_data()
    new_id = await db.add_template(data["title"], body)
    await state.clear()
    if new_id:
        await say(message, f"✅ Шаблон «{escape_html(data['title'])}» создан.")
    else:
        await say(message, "❌ Не удалось сохранить шаблон.")


@router.callback_query(F.data.startswith("tpl:del:"))
async def tpl_del(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await db.delete_template(int(callback.data.split(":")[-1]))
    await callback.answer("Удалён")
    await _show_templates(callback)


@router.callback_query(F.data.startswith("tpl:send:"))
async def tpl_send_choose_student(callback: CallbackQuery, state: FSMContext):
    """Отправка шаблона: выбрать ученика → сейчас или отложить."""
    if not await check_admin(callback):
        return
    tpl_id = int(callback.data.split(":")[-1])
    templates = {t["id"]: t for t in await db.get_templates()}
    tpl = templates.get(tpl_id)
    if not tpl:
        await callback.answer("Шаблон не найден", show_alert=True)
        return
    await state.update_data(tpl_id=tpl_id)
    students = await db.get_all_students()
    if not students:
        await callback.answer("Учеников нет", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for s in students[:20]:
        builder.button(
            text=f"👤 {s['full_name'][:28]}",
            callback_data=f"tpl:to:{s['user_id']}",
        )
    builder.button(text="◀️ Ещё", callback_data="admin:tpl")
    builder.adjust(1)
    await callback.message.edit_text("Кому отправить?", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("tpl:to:"))
async def tpl_send_when(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    student_id = int(callback.data.split(":")[-1])
    student = await db.get_student(student_id)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return
    await state.update_data(student_id=student_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить сейчас", callback_data="tpl:now")
    builder.button(text="⏰ Отложить (ввести время)", callback_data="tpl:delay")
    builder.button(text="◀️ Ещё", callback_data="admin:tpl")
    builder.adjust(1)
    await callback.message.edit_text(
        f"Отправить «{escape_html((await state.get_data()).get('tpl_id') and next((t['title'] for t in await db.get_templates() if t['id'] == (await state.get_data())['tpl_id']), ''))}» "
        f"ученику {escape_html(student['full_name'])}?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "tpl:now")
async def tpl_send_now(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    data = await state.get_data()
    await state.clear()
    tpl = next((t for t in await db.get_templates() if t["id"] == data.get("tpl_id")), None)
    student = await db.get_student(data.get("student_id")) if data.get("student_id") else None
    if not tpl or not student:
        await callback.answer("Данные потеряны", show_alert=True)
        return
    text = tpl["text"].replace("{name}", student["full_name"].split()[0])
    try:
        await callback.bot.send_message(student["user_id"], text)
        await callback.answer("Отправлено")
        await callback.message.edit_text(
            f"✅ Отправлено: {escape_html(student['full_name'])}"
        )
    except Exception as e:
        logger.warning("tpl send: %s", e)
        await callback.answer("Не доставлено", show_alert=True)


@router.callback_query(F.data == "tpl:delay")
async def tpl_send_delayed(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(DelayStates.when)
    await callback.message.edit_text(
        "⏰ Когда отправить? Введите дату и время:\n"
        "ГГГГ-ММ-ДД ЧЧ:ММ (например 2026-09-01 18:30)\n\n"
        "Или «через 2ч», «через 30м».",
        reply_markup=cancel_flow_kb(),
    )


@router.message(DelayStates.when)
async def tpl_delay_save(message: Message, state: FSMContext):
    from services.cleanup import say
    from utils.helpers import is_cancel

    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Отправка отменена.")
        return
    raw = (message.text or "").strip()
    when = _parse_when(raw)
    if when is None:
        await say(message, "❌ Не понял время. Примеры: 2026-09-01 18:30, «через 2ч», «через 30м»:")
        return
    data = await state.get_data()
    await state.clear()
    tpl = next((t for t in await db.get_templates() if t["id"] == data.get("tpl_id")), None)
    student = await db.get_student(data.get("student_id")) if data.get("student_id") else None
    if not tpl or not student:
        await say(message, "❌ Данные потеряны, начните заново.")
        return
    text = tpl["text"].replace("{name}", student["full_name"].split()[0])
    mid = await db.schedule_message(student["user_id"], text, when.strftime("%Y-%m-%d %H:%M"))
    if mid:
        await say(
            message,
            f"⏰ Отложено на {when:%d.%m %H:%M} → {escape_html(student['full_name'])}",
        )
    else:
        await say(message, "❌ Не удалось отложить.")


def _parse_when(raw: str):
    """'ГГГГ-ММ-ДД ЧЧ:ММ' | 'через 2ч' | 'через 30м' → datetime|None."""
    from datetime import timedelta

    raw = raw.lower().replace("через ", "").strip()
    try:
        if "ч" in raw or "м" in raw or "h" in raw:
            total = 0
            num = ""
            for ch in raw:
                if ch.isdigit():
                    num += ch
                else:
                    if num:
                        total += int(num) * (60 if ch in "чh" else 1)
                        num = ""
            if num:
                total += int(num)
            if total > 0:
                return datetime.now() + timedelta(minutes=total)
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    except Exception:
        return None
    return None


# =================== ОТЛОЖЕННЫЕ СООБЩЕНИЯ ===================
@router.callback_query(F.data == "admin:delayed")
async def delayed_menu(callback: CallbackQuery, state: FSMContext | None = None):
    if not await check_admin(callback):
        return
    if state:
        await state.clear()
    items = await db.get_pending_scheduled()
    builder = InlineKeyboardBuilder()
    text = "⏰ <b>Отложенные сообщения</b>\n\n"
    if not items:
        text += "Пусто. Создаются из шаблонов («Отправить → Отложить»)."
    for m in items[:10]:
        who = m.get("full_name") or str(m["student_id"])
        text += f"• {m['send_at'][:16]} → {escape_html(str(who))}\n"
        builder.button(text=f"🗑 {m['send_at'][5:16]}", callback_data=f"dl:del:{m['id']}")
    builder.button(text="◀️ Ещё", callback_data="admin:more")
    builder.adjust(2, 1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("dl:del:"))
async def delayed_del(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await db.delete_scheduled(int(callback.data.split(":")[-1]))
    await callback.answer("Отменено")
    await delayed_menu(callback)


# =================== МАТЕРИАЛЫ ===================
@router.callback_query(F.data == "admin:mat")
async def mat_menu(callback: CallbackQuery, state: FSMContext | None = None):
    if not await check_admin(callback):
        return
    if state:
        await state.clear()
    items = await db.get_materials()
    builder = InlineKeyboardBuilder()
    text = "📂 <b>Материалы</b>\n\n"
    if not items:
        text += "Пусто. Загрузите файлы — ученики увидят их в меню «📂 Материалы»."
    for m in items[:10]:
        subj = f" · {m['subject_name']}" if m.get("subject_name") else ""
        text += f"• {escape_html(m['title'])}{subj}\n"
        builder.button(text=f"🗑 {m['title'][:20]}", callback_data=f"mat:del:{m['id']}")
    builder.button(text="➕ Загрузить файл", callback_data="admin:mat:add")
    builder.button(text="◀️ Ещё", callback_data="admin:more")
    builder.adjust(2, 2, 2, 2, 1, 1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "admin:mat:add")
async def mat_add(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(MatStates.title)
    await callback.message.edit_text(
        "📂 Название материала (например «Конспект: квадратные уравнения»):",
        reply_markup=cancel_flow_kb(),
    )


@router.message(MatStates.title)
async def mat_title(message: Message, state: FSMContext):
    from services.cleanup import say
    from utils.helpers import is_cancel

    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Загрузка отменена.")
        return
    title = (message.text or "").strip()[:150]
    if not title:
        await say(message, "❌ Название не может быть пустым:")
        return
    await state.update_data(title=title)
    await state.set_state(MatStates.file)
    await say(message, "📎 Теперь отправьте сам файл (документ/фото/аудио):")


@router.message(MatStates.file, F.document | F.photo | F.audio | F.video)
async def mat_file(message: Message, state: FSMContext):
    from services.cleanup import say

    data = await state.get_data()
    await state.clear()
    if message.document:
        file_id = message.document.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    elif message.audio:
        file_id = message.audio.file_id
    else:
        file_id = message.video.file_id
    new_id = await db.add_material(data["title"], file_id)
    if new_id:
        await say(message, f"✅ Материал «{escape_html(data['title'])}» загружен.")
    else:
        await say(message, "❌ Не удалось сохранить.")


@router.message(MatStates.file)
async def mat_file_wrong(message: Message, state: FSMContext):
    from services.cleanup import say

    await say(message, "❌ Пришлите именно файл (документ/фото/аудио/видео):")


@router.callback_query(F.data.startswith("mat:del:"))
async def mat_del(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await db.delete_material(int(callback.data.split(":")[-1]))
    await callback.answer("Удалён")
    await mat_menu(callback, state=None)
