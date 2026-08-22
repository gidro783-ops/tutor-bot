
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

# ИСПРАВЛЕНИЕ (v2): SkipHandler нужен, чтобы «выбивать» пользователя
# из сценария ввода при нажатии другой кнопки/команды.
try:
    from aiogram.dispatcher.event.handler import SkipHandler
except ImportError:  # на случай другой версии aiogram
    try:
        from aiogram.exceptions import SkipHandler
    except ImportError:
        class SkipHandler(Exception):
            pass

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

def _cancel_kb():
    """Кнопка «❌ Отмена» для любого шага ввода."""
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="cancel")
    return b.as_markup()

def _cancel_line(text: str) -> str:
    """Подсказка про выход из ввода в подсказках."""
    return text + "\n\n(«отмена» — выйти из ввода)"

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
    await cb.message.edit_text(
        _cancel_line("➕ <b>Добавить слот</b>\n\nВведите дату (ГГГГ-ММ-ДД, например 2026-09-01):"),
        reply_markup=_cancel_kb()
    )

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
    await cb.message.edit_text(
        _cancel_line("🔄 День недели (0-6, 0=Пн ... 6=Вс):"),
        reply_markup=_cancel_kb()
    )

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
    # ДЗ доступны и на Free — лимит 5 в месяц проверяется при создании
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
    # ИСПРАВЛЕНИЕ: сюда попадают и счета, которые ученик уже пометил
    # («Я оплатил») — репетитору остаётся только подтвердить поступление
    rs = await db.get_reported_payments()
    if not ps and not rs:
        await cb.message.edit_text("✅ Нет счетов, ожидающих оплаты.", reply_markup=back_button("admin:payments"))
        return
    b = InlineKeyboardBuilder()
    txt = f"⏳ <b>Ожидают оплаты:</b> ({len(ps) + len(rs)})\n\n"
    for p in ps[:15]:
        nm = escape_html(p.get("full_name") or p.get("username") or str(p["student_id"]))
        txt += f"💳 #{p['id']} {nm} — {p['amount']}₽\n"
        b.button(text=f"✅ Оплачен #{p['id']}", callback_data=f"admin:pay:mark:{p['id']}")
    for p in rs[:15]:
        nm = escape_html(p.get("full_name") or p.get("username") or str(p["student_id"]))
        txt += f"🔔 #{p['id']} {nm} — {p['amount']}₽ (ученик оплатил)\n"
        b.button(text=f"✅ Подтвердить #{p['id']}", callback_data=f"admin:pay:mark:{p['id']}")
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
    # ИСПРАВЛЕНО: показываем все активные записи (pending + confirmed),
    # а не только 'confirmed'
    from utils.helpers import visible_bookings
    all_bookings = await db.get_student_bookings(cb.from_user.id)
    bs = visible_bookings(all_bookings)
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
    if p.get("status") != "pending":
        await cb.answer("Этот счёт уже оплачен или отмечен как оплаченный", show_alert=True)
        return
    # ИСПРАВЛЕНИЕ: фиксируем статус 'reported'. Без этого счёт оставался
    # 'pending' навсегда и бот каждый день снова слал ученику
    # «напоминание об оплате», а в статистике платежи не закрывались.
    await db.report_payment_paid(pid)
    nm = escape_html(p.get("full_name") or p.get("username") or str(cb.from_user.id))
    # Подтверждение репетитору с полным описанием
    for aid in config.ADMIN_IDS:
        try:
            await cb.bot.send_message(
                aid,
                f"💳 <b>Ученик сообщил об оплате!</b>\n\n"
                f"👤 {nm}\n"
                f"💰 Сумма: {p['amount']}₽\n"
                f"📋 {escape_html(p.get('description') or '—')}\n"
                f"🆔 Счёт #{pid}\n\n"
                f"Проверьте поступление и подтвердите: "
                f"/admin → Оплаты → «⏳ Ожидают оплаты»"
            )
        except Exception as e:
            logger.warning(f"[pay_paid] notify admin {aid}: {e}")
    await cb.answer("✅ Подтверждение отправлено репетитору!", show_alert=True)
    # Ученику — понятный статус
    await cb.message.edit_text(
        f"⏳ <b>Оплата счёта #{pid} сообщена.</b>\n\n"
        f"Репетитор получил уведомление и проверит поступление. "
        f"Как только подтвердит оплату — счёт будет закрыт 🎉"
    )

# ===== ЕДИНЫЙ FSM-ВВОД =====
@router.message(Step.flow)
async def step_input(message: Message, state: FSMContext):
    data = await state.get_data()
    flow, step = data.get("flow"), data.get("step")
    v = (message.text or "").strip()
    low = v.lower()

    # ===== ИСПРАВЛЕНИЕ (v2): ВЫХОД ИЗ СЦЕНАРИЯ ВВОДА =====
    # Раньше: открыв ввод (например «Повторяющиеся слоты»), нельзя было
    # выйти — бот ждал дату/время, а нажатия других кнопок «глотались».
    # Теперь:
    #  - «отмена»/«cancel»/кнопка «❌ Отмена» → просто выходим из ввода;
    #  - любая команда (/start, /admin ...) или кнопка главного меню →
    #    ввод сбрасывается и выполняется ТОЛЬКО вторая нажатая кнопка
    #    (событие передаётся дальше следующим обработчикам).
    CANCEL_WORDS = {"❌ отмена", "отмена", "отменить", "cancel"}
    MENU_BUTTONS = {
        "📅 записаться на занятие", "📋 мои занятия", "📝 домашние задания",
        "💳 оплата", "❓ faq", "🎁 пригласить друга", "👤 мой профиль",
        "📞 связаться с репетитором",
    }
    if low in CANCEL_WORDS or v == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Ввод отменён.\n"
            "Нажмите нужный пункт меню."
        )
        return
    if low in MENU_BUTTONS or v.startswith("/"):
        await state.clear()
        raise SkipHandler()

    if flow == "slot":
        if step == "date":
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                await message.answer("❌ Формат ГГГГ-ММ-ДД (например 2026-09-01):")
                return
            await state.update_data(step="start", date=v)
            await message.answer(_cancel_line("🕐 Время начала (ЧЧ:ММ):"), reply_markup=_cancel_kb())
            return
        if step == "start":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                await message.answer("❌ Формат ЧЧ:ММ (например 15:00):")
                return
            await state.update_data(step="end", start=v)
            await message.answer(_cancel_line("🕐 Время окончания (ЧЧ:ММ):"), reply_markup=_cancel_kb())
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
            await message.answer(_cancel_line("🕐 Время начала (ЧЧ:ММ):"), reply_markup=_cancel_kb())
            return
        if step == "start":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                await message.answer("❌ Формат ЧЧ:ММ:")
                return
            await state.update_data(step="end", start=v)
            await message.answer(_cancel_line("🕐 Время окончания (ЧЧ:ММ):"), reply_markup=_cancel_kb())
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
