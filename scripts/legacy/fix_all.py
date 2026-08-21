# -*- coding: utf-8 -*-
"""fix_all.py — ОДНИМ запуском чинит все кнопки бота. Запуск: python fix_all.py"""
import os, io, py_compile

def read_blocks(raw):
    blocks = []
    i = 0
    while True:
        i = raw.find("<<<PATCH:", i)
        if i == -1:
            break
        j = raw.find(">>>", i)
        name = raw[i + len("<<<PATCH:"):j]
        k = raw.find("<<<OLD>>>", j)
        l = raw.find("<<<END_OLD>>>", k)
        old = raw[k + len("<<<OLD>>>"):l]
        m = raw.find("<<<NEW>>>", l)
        n = raw.find("<<<END_NEW>>>", m)
        new = raw[m + len("<<<NEW>>>"):n]
        blocks.append((name, old, new))
        i = n
    return blocks

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    ok = True
    hdir = os.path.join(base, "handlers")
    if not os.path.isdir(hdir):
        print("X Папка handlers не найдена! Запустите из папки проекта (где main.py).")
        return
    io.open(os.path.join(hdir, "fixes.py"), "w", encoding="utf-8").write(_FIXES)
    print("OK создан handlers/fixes.py")
    for path, old, new in read_blocks(_DATA):
        if "<<<KEEP_UNTIL>>>" in old:
            start_marker = old.split("\n<<<KEEP_UNTIL>>>")[0]
            end_marker = new
            full = os.path.join(base, path)
            src = io.open(full, encoding="utf-8").read()
            si = src.find(start_marker)
            ei = src.find(end_marker, si)
            if si == -1 or ei == -1:
                print("X блок не найден в", path)
                ok = False
                continue
            src = src[:si] + src[ei:]
            io.open(full, "w", encoding="utf-8").write(src)
            print("OK", path, "(удалён дубликат admin:referrals)")
            continue
        full = os.path.join(base, path)
        if not os.path.exists(full):
            print("X файл не найден:", path)
            ok = False
            continue
        src = io.open(full, encoding="utf-8").read()
        if old not in src:
            print("X фрагмент не найден в", path, "- пропущено (возможно, уже исправлено)")
            ok = False
            continue
        src = src.replace(old, new, 1)
        io.open(full, "w", encoding="utf-8").write(src)
        print("OK", path)
    files = ["main.py", "handlers/__init__.py", "handlers/fixes.py", "handlers/admin.py",
             "handlers/student.py", "handlers/mailing.py", "handlers/payments.py",
             "handlers/referral.py", "keyboards/admin_kb.py", "utils/helpers.py",
             "services/userbot.py"]
    for f in files:
        try:
            py_compile.compile(os.path.join(base, f), doraise=True)
        except Exception as e:
            print("X ОШИБКА КОМПИЛЯЦИИ:", f, e)
            ok = False
    print()
    if ok:
        print("ГОТОВО! Все кнопки исправлены. Дальше в PowerShell:")
        print("  git add .")
        print("  git commit -m 'fix buttons'")
        print("  git push")
    else:
        print("Были пропуски - пришлите этот вывод.")

_DATA = r'''
<<<PATCH:handlers/__init__.py>>>
<<<OLD>>>from handlers.admin import router as admin_router
from handlers.student import router as student_router<<<END_OLD>>>
<<<NEW>>>from handlers.admin import router as admin_router
from handlers.fixes import router as fixes_router
from handlers.student import router as student_router<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/__init__.py>>>
<<<OLD>>>    "admin_router",
    "student_router",<<<END_OLD>>>
<<<NEW>>>    "admin_router",
    "fixes_router",
    "student_router",<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:main.py>>>
<<<OLD>>>    dp.include_router(admin_router)
    dp.include_router(booking_router)<<<END_OLD>>>
<<<NEW>>>    dp.include_router(admin_router)
    dp.include_router(fixes_router)
    dp.include_router(booking_router)<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:main.py>>>
<<<OLD>>>    referral_router,
)<<<END_OLD>>>
<<<NEW>>>    referral_router,
    fixes_router,
)<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:keyboards/admin_kb.py>>>
<<<OLD>>>        ("📢 Рассылки", "admin:mailings"),
        ("❓ FAQ", "admin:faq"),
        ("📊 Аналитика", "admin:analytics"),<<<END_OLD>>>
<<<NEW>>>        ("📢 Рассылки", "admin:mailings"),
        ("📊 Аналитика", "admin:analytics"),<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/admin.py>>>
<<<OLD>>>    await db.set_dnd(True)
    await callback.message.edit_text("✅ DND включён.")<<<END_OLD>>>
<<<NEW>>>    await db.set_dnd(True)
    await callback.message.edit_text("✅ DND включён.", reply_markup=admin_dnd_menu())<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/admin.py>>>
<<<OLD>>>    await db.set_dnd(False)
    await callback.message.edit_text("🔔 DND выключен.")<<<END_OLD>>>
<<<NEW>>>    await db.set_dnd(False)
    await callback.message.edit_text("🔔 DND выключен.", reply_markup=admin_dnd_menu())<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/student.py>>>
<<<OLD>>>    builder.button(text="📞 Указать телефон", callback_data="profile:phone")<<<END_OLD>>>
<<<NEW>>>    phone_btn = "📞 Изменить телефон" if student.get("phone") else "📞 Указать телефон"
    builder.button(text=phone_btn, callback_data="profile:phone")<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:utils/helpers.py>>>
<<<OLD>>>    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    if not re.match(r'^[\+]?[0-9]{7,20}$', cleaned):<<<END_OLD>>>
<<<NEW>>>    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
    if not re.match(r'^[\+]?[0-9]{5,20}$', cleaned):<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/mailing.py>>>
<<<OLD>>>class NewMailingFlow(StatesGroup):
    text = State()
    target = State()
    confirm = State()<<<END_OLD>>>
<<<NEW>>>class NewMailingFlow(StatesGroup):
    text = State()
    target = State()
    delay = State()
    confirm = State()<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/mailing.py>>>
<<<OLD>>>    data = await state.get_data()
    mailing_text = data.get("text", "")
    # Предпросмотр + подтверждение
    await state.update_data(target=target)
    await state.set_state(NewMailingFlow.confirm)
    target_label = "Все ученики" if target == "all" else "Неактивные"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="mail:confirm:yes")
    builder.button(text="❌ Отмена", callback_data="mail:cancel")
    builder.adjust(2)
    await callback.message.edit_text(
        f"📢 <b>Предпросмотр рассылки</b>\n\n"
        f"📝 Текст:\n{escape_html(mailing_text[:500])}\n\n"
        f"👥 Цель: {target_label}\n\n"
        f"Подтвердите отправку:",
        reply_markup=builder.as_markup()
    )<<<END_OLD>>>
<<<NEW>>>    data = await state.get_data()
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
    )<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/mailing.py>>>
<<<OLD>>>@router.callback_query(F.data == "mail:confirm:yes")
async def mailing_confirm(callback: CallbackQuery, state: FSMContext):
    """Отправка рассылки с соблюдением лимитов."""
    data = await state.get_data()
    text = data.get("text", "")
    target = data.get("target", "all")
    await state.clear()<<<END_OLD>>>
<<<NEW>>>@router.callback_query(F.data.startswith("mail:delay:"))
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
    await state.clear()<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/mailing.py>>>
<<<OLD>>>    # ИСПРАВЛЕНО: проверяем лимит MAX_MAILING_PER_DAY
    if len(students_list) > config.MAX_MAILING_PER_DAY:
        students_list = students_list[:config.MAX_MAILING_PER_DAY]
        logger.warning(
            f"Mailing truncated to {config.MAX_MAILING_PER_DAY} (MAX_MAILING_PER_DAY)"
        )
<<<END_OLD>>>
<<<NEW>>><<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/mailing.py>>>
<<<OLD>>>            await callback.bot.send_message(student["user_id"], text)
            sent += 1
            # ИСПРАВЛЕНО: задержка из конфига (было неиспользуемое значение)
            await asyncio.sleep(config.MAILING_DELAY_SECONDS)<<<END_OLD>>>
<<<NEW>>>            await callback.bot.send_message(student["user_id"], text)
            sent += 1
            await asyncio.sleep(delay)<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:services/userbot.py>>>
<<<OLD>>>    async def send_message_safe(self, chat_id: int, text: str) -> bool:
        """Безопасная отправка сообщения с рандомной задержкой."""
        if not self.is_connected or not self.client:
            return False
        try:
            delay = random.uniform(5, 30)
            await asyncio.sleep(delay)
            await self.client.send_message(chat_id, text)
            logger.info(f"✅ Userbot: сообщение отправлено в чат {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Userbot: ошибка отправки в чат {chat_id}: {e}")
            return False<<<END_OLD>>>
<<<NEW>>>    async def send_message_safe(self, chat_id: int, text: str) -> bool:
        """Безопасная отправка сообщения с рандомной задержкой.

        ИСПРАВЛЕНО: обрабатываем FloodWaitError (лимит Telegram) —
        ждём нужное время и повторяем вместо мгновенного отказа.
        """
        if not self.is_connected or not self.client:
            return False
        try:
            from telethon.errors import FloodWaitError
        except ImportError:
            FloodWaitError = None
        try:
            delay = random.uniform(5, 30)
            await asyncio.sleep(delay)
            try:
                await self.client.send_message(chat_id, text)
            except FloodWaitError as e:
                wait = int(e.seconds)
                if wait > 3600:
                    logger.warning(
                        f"Userbot: flood-wait {wait}с в чат {chat_id} — пропускаем"
                    )
                    return False
                logger.info(f"Userbot: flood-wait {wait}с, ждём и повторяем...")
                await asyncio.sleep(wait + 5)
                await self.client.send_message(chat_id, text)
            logger.info(f"✅ Userbot: сообщение отправлено в чат {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Userbot: ошибка отправки в чат {chat_id}: {e}")
            return False<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/payments.py>>>
<<<OLD>>>    text = "💳 <b>Неоплаченные счета:</b>\n\n"
    for p in payments:
        text += f"• {p['amount']}₽ — {escape_html(p.get('description', ''))}\n"
    await message.answer(text)<<<END_OLD>>>
<<<NEW>>>    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    text = "💳 <b>Неоплаченные счета:</b>\n\n"
    for p in payments:
        text += f"• #{p['id']} {p['amount']}₽ — {escape_html(p.get('description', ''))}\n"
        builder.button(text=f"✅ Я оплатил #{p['id']}", callback_data=f"payment:paid:{p['id']}")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup())<<<END_NEW>>>
<<<END_PATCH>>>
<<<PATCH:handlers/referral.py>>>
<<<OLD>>># =================== АДМИН: список рефералов ===================
<<<KEEP_UNTIL>>>
<<<END_OLD>>>
<<<NEW>>># =================== АДМИН: применить бонус ===================<<<END_NEW>>>
<<<END_PATCH>>>
'''

_FIXES = r'''
"""Недостающие обработчики кнопок (фиксы)."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta, date as date_type
from config import config
from database import db
from keyboards.admin_kb import admin_homework_menu, back_button, student_list_keyboard
from keyboards.student_kb import my_bookings_keyboard, booking_detail_keyboard
from utils.helpers import format_date, escape_html
import logging
logger = logging.getLogger(__name__)
router = Router()

class Step(StatesGroup):
    flow = State()

async def _adm(cb: CallbackQuery) -> bool:
    if cb.from_user.id not in config.ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return False
    try:
        if not await db.check_admin_session(cb.from_user.id):
            await cb.answer("Сессия истекла. Введите /admin", show_alert=True)
            return False
    except Exception:
        pass
    return True

async def _set_flow(state: FSMContext, flow: str, step: str, **kw):
    await state.clear()
    await state.set_state(Step.flow)
    await state.update_data(flow=flow, step=step, **kw)

# ===== ОБЩАЯ ОТМЕНА =====
@router.callback_query(F.data == "cancel")
async def g_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Действие отменено.")
    if cb.from_user.id in config.ADMIN_IDS:
        try:
            if await db.check_admin_session(cb.from_user.id):
                from handlers.admin import show_admin_panel
                await show_admin_panel(cb.message)
        except Exception:
            pass

# ===== РАСПИСАНИЕ =====
@router.callback_query(F.data == "admin:schedule:week")
async def sched_week(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await state.clear()
    t = date_type.today()
    txt = "📆 <b>Расписание на неделю:</b>\n\n"
    for i in range(7):
        d = t + timedelta(days=i)
        sl = await db.get_slots_for_date(d.isoformat())
        line = "—" if not sl else " ".join(f"{'✅' if s['is_available'] else '🔒'}{s['start_time'][:5]}-{s['end_time'][:5]}" for s in sl)
        txt += f"<b>{format_date(d.isoformat())}</b>: {line}\n"
    await cb.message.edit_text(txt, reply_markup=back_button("admin:schedule"))

@router.callback_query(F.data == "admin:schedule:add_slot")
async def slot_add(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await _set_flow(state, "slot", "date")
    await cb.message.edit_text("➕ <b>Добавить слот</b>\n\nВведите дату (ГГГГ-ММ-ДД, например 2026-09-01):")

@router.callback_query(F.data == "admin:schedule:recurring")
async def sched_rec(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await state.clear()
    try:
        cur = await db.db.execute("SELECT * FROM time_slots WHERE is_recurring = 1 ORDER BY recurring_day")
        rows = await cur.fetchall()
        tpl = [dict(r) for r in rows]
    except Exception:
        tpl = []
    days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    if not tpl:
        txt = "🔄 <b>Повторяющиеся слоты</b>\n\nШаблонов пока нет."
    else:
        txt = "🔄 <b>Повторяющиеся слоты:</b>\n\n" + "\n".join(
            f"• {days_ru[t['recurring_day']] if t['recurring_day'] is not None else '?'} {t['start_time'][:5]}-{t['end_time'][:5]}" for t in tpl)
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить шаблон", callback_data="admin:schedule:recurring:add")
    b.button(text="◀️ Назад", callback_data="admin:schedule")
    b.adjust(1)
    await cb.message.edit_text(txt, reply_markup=b.as_markup())

@router.callback_query(F.data == "admin:schedule:recurring:add")
async def rec_add(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await _set_flow(state, "rec", "weekday")
    await cb.message.edit_text("🔄 День недели (0-6, 0=Пн ... 6=Вс):")

@router.callback_query(F.data == "admin:schedule:block")
async def sched_block(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await state.clear()
    t = date_type.today()
    b = InlineKeyboardBuilder()
    txt = "🚫 <b>Заблокировать/разблокировать слот</b>\n\n"
    any_slots = False
    for i in range(7):
        d = t + timedelta(days=i)
        sl = await db.get_slots_for_date(d.isoformat())
        if not sl: continue
        any_slots = True
        txt += f"<b>{format_date(d.isoformat())}:</b>\n"
        for s in sl:
            free = s["is_available"]
            txt += f"{'✅' if free else '🔒'} {s['start_time'][:5]}-{s['end_time'][:5]}\n"
            pre = "unblock" if not free else "block"
            act = "🔓 Разблокировать" if not free else "🔒 Заблокировать"
            b.button(text=f"{act} {s['start_time'][:5]}", callback_data=f"admin:slot:{pre}:{s['id']}")
        txt += "\n"
    if not any_slots: txt += "📭 Слотов на неделю нет."
    b.button(text="◀️ Назад", callback_data="admin:schedule")
    b.adjust(1)
    await cb.message.edit_text(txt, reply_markup=b.as_markup())

@router.callback_query(F.data.startswith("admin:slot:block:"))
async def slot_block(cb: CallbackQuery):
    if not await _adm(cb): return
    await db.block_slot(int(cb.data.split(":")[-1]))
    await cb.answer("🔒 Заблокирован")
    await cb.message.edit_text("🔒 Слот заблокирован.", reply_markup=back_button("admin:schedule:block"))

@router.callback_query(F.data.startswith("admin:slot:unblock:"))
async def slot_unblock(cb: CallbackQuery):
    if not await _adm(cb): return
    await db.unblock_slot(int(cb.data.split(":")[-1]))
    await cb.answer("✅ Разблокирован")
    await cb.message.edit_text("✅ Слот разблокирован.", reply_markup=back_button("admin:schedule:block"))

# ===== ДОМАШНИЕ ЗАДАНИЯ (АДМИН) =====
@router.callback_query(F.data == "admin:homework")
async def adm_hw_menu(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await state.clear()
    await cb.message.edit_text("📝 <b>Домашние задания</b>", reply_markup=admin_homework_menu())

@router.callback_query(F.data == "admin:hw:list")
async def adm_hw_list(cb: CallbackQuery):
    if not await _adm(cb): return
    hw = await db.get_all_homework()
    if not hw:
        await cb.message.edit_text("📭 Заданий нет.", reply_markup=back_button("admin:homework"))
        return
    st = {"assigned": "📝", "submitted": "📤", "graded": "✅"}
    txt = "📝 <b>Все задания:</b>\n\n" + "\n".join(f"{st.get(h['status'], '❔')} #{h['id']} {escape_html(h['title'][:40])}" for h in hw[:20])
    await cb.message.edit_text(txt, reply_markup=back_button("admin:homework"))

@router.callback_query(F.data == "admin:hw:pending")
async def adm_hw_pending(cb: CallbackQuery):
    if not await _adm(cb): return
    hw = await db.get_pending_homework()
    if not hw:
        await cb.message.edit_text("📭 На проверке ничего нет.", reply_markup=back_button("admin:homework"))
        return
    b = InlineKeyboardBuilder()
    txt = "📤 <b>На проверке:</b>\n\n"
    for h in hw[:20]:
        txt += f"#{h['id']} {escape_html(h['title'][:40])}\n"
        b.button(text=f"✅ Оценить #{h['id']}", callback_data=f"admin:hw:grade:{h['id']}")
    b.button(text="◀️ Назад", callback_data="admin:homework")
    b.adjust(1)
    await cb.message.edit_text(txt, reply_markup=b.as_markup())

# ===== ОПЛАТЫ =====
@router.callback_query(F.data == "admin:pay:pending")
async def adm_pay_pending(cb: CallbackQuery):
    if not await _adm(cb): return
    ps = await db.get_pending_payments()
    if not ps:
        await cb.message.edit_text("✅ Нет счетов, ожидающих оплаты.", reply_markup=back_button("admin:payments"))
        return
    b = InlineKeyboardBuilder()
    txt = f"⏳ <b>Ожидают оплаты:</b> ({len(ps)})\n\n"
    for p in ps[:15]:
        nm = escape_html(p.get("full_name") or p.get("username") or str(p["student_id"]))
        txt += f"💳 #{p['id']} {nm} — {p['amount']}₽\n"
        b.button(text=f"✅ Оплачен #{p['id']}", callback_data=f"admin:pay:mark:{p['id']}")
    b.button(text="◀️ Назад", callback_data="admin:payments")
    b.adjust(1)
    await cb.message.edit_text(txt, reply_markup=b.as_markup())

# ===== УВЕДОМЛЕНИЯ =====
@router.callback_query(F.data == "admin:notifications")
async def adm_notif(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await state.clear()
    try:
        dnd_on, _ = await db.is_dnd_active()
    except Exception:
        dnd_on = False
    txt = ("🔔 <b>Уведомления</b>\n\n"
        f"⏰ Напоминания о занятиях: за {', '.join(str(m) + ' мин' for m in config.REMINDER_BEFORE_MINUTES)}\n"
        f"☀️ Утренняя сводка: 8:00\n💳 Напоминания об оплате: 10:00\n"
        f"🔕 DND: {'ВКЛЮЧЕН' if dnd_on else 'выключен'} ({config.DND_START}—{config.DND_END})\n\n"
        f"Изменения — в .env: REMINDER_BEFORE_MINUTES, DND_START, DND_END, TIMEZONE.")
    b = InlineKeyboardBuilder()
    b.button(text="🔕 Настроить DND", callback_data="admin:dnd")
    b.button(text="◀️ Назад", callback_data="admin:back")
    b.adjust(1)
    await cb.message.edit_text(txt, reply_markup=b.as_markup())

# ===== DND: РАСПИСАНИЕ =====
@router.callback_query(F.data == "admin:dnd:schedule")
async def dnd_sched(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await _set_flow(state, "dnd", "start")
    await cb.message.edit_text(f"⚙️ <b>DND</b> (сейчас {config.DND_START}—{config.DND_END})\n\nВремя начала (ЧЧ:ММ):")

# ===== A/B ТЕСТЫ =====
@router.callback_query(F.data == "admin:ab_tests")
async def adm_ab(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await state.clear()
    ts = await db.get_active_ab_tests()
    if not ts:
        txt = "🧪 <b>A/B тесты</b>\n\nАктивных тестов нет."
    else:
        txt = "🧪 <b>A/B тесты:</b>\n\n" + "\n".join(
            f"• {escape_html(t['name'])}: A:{t.get('variant_a_sends', 0)}📤/{t.get('variant_a_clicks', 0)}🖱 B:{t.get('variant_b_sends', 0)}📤/{t.get('variant_b_clicks', 0)}🖱" for t in ts)
    b = InlineKeyboardBuilder()
    b.button(text="➕ Создать тест", callback_data="admin:ab:create")
    b.button(text="◀️ Назад", callback_data="admin:back")
    b.adjust(1)
    await cb.message.edit_text(txt, reply_markup=b.as_markup())

@router.callback_query(F.data == "admin:ab:create")
async def ab_create(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await _set_flow(state, "ab", "name")
    await cb.message.edit_text("🧪 Название теста:")

# ===== УЧЕНИКИ =====
@router.callback_query(F.data == "admin:students:search")
async def students_search(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await _set_flow(state, "search", "query")
    await cb.message.edit_text("🔍 Введите имя, username или ID ученика:")

@router.callback_query(F.data == "admin:students:stats")
async def students_stats(cb: CallbackQuery):
    if not await _adm(cb): return
    ss = await db.get_all_students()
    d = await db.get_dashboard_stats()
    act = sum(1 for s in ss if s.get("is_active", 1))
    src = {}
    for s in ss:
        k = s.get("source") or "direct"
        src[k] = src.get(k, 0) + 1
    txt = ("📊 <b>Статистика учеников</b>\n\n"
        f"👥 Всего: {len(ss)}\n✅ Активных: {act}\n💤 Неактивных: {len(ss) - act}\n"
        f"📈 Новых за месяц: {d.get('new_students_month', 0)}\n"
        f"📌 Источники: {', '.join(f'{k}: {v}' for k, v in src.items()) or '—'}")
    await cb.message.edit_text(txt, reply_markup=back_button("admin:students"))

@router.callback_query(F.data == "admin:students:reactivate")
async def students_reactivate(cb: CallbackQuery):
    if not await _adm(cb): return
    inc = await db.get_inactive_students(days=90)
    if not inc:
        await cb.message.edit_text("✅ Нет неактивных учеников.", reply_markup=back_button("admin:students"))
        return
    b = InlineKeyboardBuilder()
    for s in inc[:20]:
        b.button(text=f"✉️ {escape_html(s.get('full_name', '—'))}", callback_data=f"admin:student:{s['user_id']}:message")
    b.button(text="◀️ Назад", callback_data="admin:students")
    b.adjust(1)
    await cb.message.edit_text(f"💤 <b>Неактивных:</b> {len(inc)}\n\nНажмите, чтобы написать:", reply_markup=b.as_markup())

# ===== УЧЕНИК: ДЕТАЛИ =====
@router.callback_query(F.data.startswith("admin:student:") & F.data.contains(":bookings"))
async def st_bookings(cb: CallbackQuery):
    if not await _adm(cb): return
    sid = int(cb.data.split(":")[2])
    bs = await db.get_student_bookings(sid)
    if not bs:
        await cb.message.edit_text("📭 Записей нет.", reply_markup=back_button(f"admin:student:{sid}"))
        return
    st = {"pending": "⏳", "confirmed": "✅", "completed": "📗", "cancelled": "❌"}
    txt = "📅 <b>Записи:</b>\n\n" + "\n".join(f"{st.get(b.get('status'), '❔')} {b.get('date', '—')} {b.get('start_time', '')[:5]} — {b.get('booking_type', '—')}" for b in bs[:15])
    await cb.message.edit_text(txt, reply_markup=back_button(f"admin:student:{sid}"))

@router.callback_query(F.data.startswith("admin:student:") & F.data.contains(":hw"))
async def st_hw(cb: CallbackQuery):
    if not await _adm(cb): return
    sid = int(cb.data.split(":")[2])
    hw = await db.get_student_homework(sid)
    if not hw:
        await cb.message.edit_text("📭 ДЗ нет.", reply_markup=back_button(f"admin:student:{sid}"))
        return
    st = {"assigned": "📝", "submitted": "📤", "graded": "✅"}
    txt = "📝 <b>ДЗ:</b>\n\n" + "\n".join(f"{st.get(h['status'], '❔')} #{h['id']} {escape_html(h['title'][:40])}" for h in hw[:15])
    await cb.message.edit_text(txt, reply_markup=back_button(f"admin:student:{sid}"))

@router.callback_query(F.data.startswith("admin:student:") & F.data.contains(":payments"))
async def st_payments(cb: CallbackQuery):
    if not await _adm(cb): return
    sid = int(cb.data.split(":")[2])
    ps = await db.get_pending_payments(sid)
    if not ps:
        await cb.message.edit_text("💳 Счетов нет.", reply_markup=back_button(f"admin:student:{sid}"))
        return
    txt = "💳 <b>Счета:</b>\n\n" + "\n".join(f"#{p['id']} — {p['amount']}₽ — {p['status']}" for p in ps[:15])
    await cb.message.edit_text(txt, reply_markup=back_button(f"admin:student:{sid}"))

@router.callback_query(F.data.startswith("admin:student:") & F.data.contains(":message"))
async def st_message(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await _set_flow(state, "msg", "text", sid=int(cb.data.split(":")[2]))
    await cb.message.edit_text("✉️ Введите текст сообщения ученику:")

@router.callback_query(F.data.startswith("admin:student:") & F.data.contains(":deactivate"))
async def st_deactivate(cb: CallbackQuery):
    if not await _adm(cb): return
    try:
        await db.db.execute("UPDATE students SET is_active = 0 WHERE user_id = ?", (int(cb.data.split(":")[2]),))
        await db.db.commit()
        await cb.message.edit_text("🚫 Ученик деактивирован.", reply_markup=back_button("admin:students:list"))
    except Exception as e:
        logger.error(f"[st_deactivate] {e}")
        await cb.answer("Ошибка", show_alert=True)

# ===== РАССЫЛКИ: ДОБАВИТЬ ЧАТ =====
@router.callback_query(F.data == "admin:mail:add_chat")
async def mail_add_chat(cb: CallbackQuery, state: FSMContext):
    if not await _adm(cb): return
    await _set_flow(state, "chat", "id")
    await cb.message.edit_text("➕ Введите ID чата или @username:")

# ===== УЧЕНИК: МОИ ЗАНЯТИЯ =====
@router.callback_query(F.data.startswith("mybooking:"))
async def my_booking(cb: CallbackQuery):
    parts = cb.data.split(":")
    if parts[1] == "cancel":
        bk = await db.get_booking(int(parts[2]))
        if not bk or bk["student_id"] != cb.from_user.id:
            await cb.answer("Не найдено", show_alert=True)
            return
        await db.cancel_booking(int(parts[2]), reason="Отменено учеником")
        await cb.message.edit_text("❌ Занятие отменено.")
        return
    bk = await db.get_booking(int(parts[1]))
    if not bk or bk["student_id"] != cb.from_user.id:
        await cb.answer("Не найдено", show_alert=True)
        return
    txt = (f"📚 <b>Занятие #{bk['id']}</b>\n\n"
        f"📅 Дата: {bk.get('date', '—')}\n🕐 Время: {bk.get('start_time', '—')[:5]}\n"
        f"📊 Статус: {bk.get('status', '—')}\n📝 Тип: {bk.get('booking_type', '—')}")
    await cb.message.edit_text(txt, reply_markup=booking_detail_keyboard(bk["id"], bk["status"] in ("pending", "confirmed")))

@router.callback_query(F.data == "mybookings:list")
async def my_bookings_list(cb: CallbackQuery):
    bs = await db.get_student_bookings(cb.from_user.id, status="confirmed")
    if not bs:
        await cb.message.edit_text("📭 У вас пока нет записей.")
        return
    await cb.message.edit_text("📋 <b>Ваши занятия:</b>", reply_markup=my_bookings_keyboard(bs))

# ===== УЧЕНИК: Я ОПЛАТИЛ =====
@router.callback_query(F.data.startswith("payment:paid:"))
async def pay_paid(cb: CallbackQuery):
    pid = int(cb.data.split(":")[-1])
    p = await db.get_payment_by_id(pid)
    if not p or p["student_id"] != cb.from_user.id:
        await cb.answer("Не найдено", show_alert=True)
        return
    for aid in config.ADMIN_IDS:
        try:
            await cb.bot.send_message(aid, f"💳 Ученик сообщает об оплате счёта #{pid} на {p['amount']}₽. Проверьте: /admin → Оплаты.")
        except Exception as e:
            logger.warning(f"[pay_paid] {e}")
    await cb.answer("✅ Репетитор уведомлён!", show_alert=True)

# ===== ЕДИНЫЙ FSM-ВВОД =====
@router.message(Step.flow)
async def step_input(message: Message, state: FSMContext):
    data = await state.get_data()
    flow, step = data.get("flow"), data.get("step")
    v = message.text.strip()

    if flow == "slot":
        if step == "date":
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                await message.answer("❌ Формат ГГГГ-ММ-ДД (например 2026-09-01):")
                return
            await state.update_data(step="start", date=v)
            await message.answer("🕐 Время начала (ЧЧ:ММ):")
            return
        if step == "start":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                await message.answer("❌ Формат ЧЧ:ММ (например 15:00):")
                return
            await state.update_data(step="end", start=v)
            await message.answer("🕐 Время окончания (ЧЧ:ММ):")
            return
        if step == "end":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                await message.answer("❌ Формат ЧЧ:ММ:")
                return
            if v <= data["start"]:
                await message.answer("❌ Окончание должно быть позже начала:")
                return
            try:
                await db.add_time_slot(data["date"], data["start"], v)
                await state.clear()
                await message.answer(f"✅ Слот: {data['date']} {data['start']}-{v}", reply_markup=back_button("admin:schedule"))
            except Exception:
                await state.clear()
                await message.answer("❌ Ошибка. Возможно, слот уже существует.")
            return

    if flow == "rec":
        if step == "weekday":
            try:
                d = int(v)
                if d < 0 or d > 6: raise ValueError
            except ValueError:
                await message.answer("❌ Число 0-6 (0=Пн ... 6=Вс):")
                return
            await state.update_data(step="start", weekday=d)
            await message.answer("🕐 Время начала (ЧЧ:ММ):")
            return
        if step == "start":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                await message.answer("❌ Формат ЧЧ:ММ:")
                return
            await state.update_data(step="end", start=v)
            await message.answer("🕐 Время окончания (ЧЧ:ММ):")
            return
        if step == "end":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                await message.answer("❌ Формат ЧЧ:ММ:")
                return
            try:
                await db.add_time_slot("2000-01-01", data["start"], v, is_recurring=True, recurring_day=data["weekday"], slot_type="recurring_template")
                await state.clear()
                await message.answer(f"✅ Шаблон добавлен (день {data['weekday']}, {data['start']}-{v}). Слоты будут генерироваться автоматически.", reply_markup=back_button("admin:schedule"))
            except Exception:
                await state.clear()
                await message.answer("❌ Такой шаблон уже существует.")
            return

    if flow == "search":
        q = v.lower()
        found = []
        for s in await db.get_all_students():
            if q in (s.get("full_name") or "").lower() or q in (s.get("username") or "").lower() or q == str(s["user_id"]):
                found.append(s)
        await state.clear()
        if not found:
            await message.answer("🔍 Никого не найдено.", reply_markup=back_button("admin:students"))
        else:
            await message.answer(f"🔍 Найдено: {len(found)}", reply_markup=student_list_keyboard(found))
        return

    if flow == "dnd":
        if step == "start":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                await message.answer("❌ Формат ЧЧ:ММ:")
                return
            await state.update_data(step="end", start=v)
            await message.answer("Время окончания (ЧЧ:ММ):")
            return
        if step == "end":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                await message.answer("❌ Формат ЧЧ:ММ:")
                return
            await db.set_setting("dnd_start", data["start"])
            await db.set_setting("dnd_end", v)
            await state.clear()
            await message.answer(f"✅ DND настроен: {data['start']}-{v}", reply_markup=back_button("admin:dnd"))
            return

    if flow == "ab":
        if step == "name":
            await state.update_data(step="a", name=v[:100])
            await message.answer("Текст варианта A:")
            return
        if step == "a":
            await state.update_data(step="b", variant_a=v[:2000])
            await message.answer("Текст варианта B:")
            return
        if step == "b":
            try:
                await db.db.execute("INSERT INTO ab_tests (name, variant_a_text, variant_b_text) VALUES (?, ?, ?)", (data["name"], data["variant_a"], v[:2000]))
                await db.db.commit()
                await state.clear()
                await message.answer("✅ A/B тест создан!", reply_markup=back_button("admin:ab_tests"))
            except Exception as e:
                logger.error(f"[ab] {e}")
                await state.clear()
                await message.answer("❌ Ошибка создания теста.")
            return

    if flow == "chat":
        try:
            await db.add_ad_chat(v, v)
            await state.clear()
            await message.answer(f"✅ Чат {escape_html(v)} добавлен.", reply_markup=back_button("admin:mailings"))
        except Exception as e:
            logger.error(f"[chat] {e}")
            await state.clear()
            await message.answer("❌ Ошибка добавления чата.")
        return

    if flow == "msg":
        try:
            await message.bot.send_message(data["sid"], message.text)
            await state.clear()
            await message.answer("✅ Сообщение отправлено!", reply_markup=back_button("admin:students"))
        except Exception as e:
            logger.error(f"[msg] {e}")
            await state.clear()
            await message.answer("❌ Не удалось отправить (ученик не начинал диалог с ботом).")
        return
'''

if __name__ == "__main__":
    main()