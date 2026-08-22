import asyncio
from datetime import datetime, date, timedelta
from aiogram import Bot
from database import db
from config import config
from utils.texts import Texts
from utils.helpers import format_date, escape_html
from keyboards.student_kb import rating_keyboard
import logging
logger = logging.getLogger(__name__)
async def send_booking_reminders(bot: Bot):
    """Отправляет напоминания о предстоящих занятиях.
    
    ИСПРАВЛЕНО: логируем ошибки вместо silent pass.
    """
    for minutes in config.REMINDER_BEFORE_MINUTES:
        try:
            bookings = await db.get_upcoming_bookings(minutes_ahead=minutes)
        except Exception as e:
            logger.error(f"[send_booking_reminders] Failed to get bookings: {e}")
            continue
        for booking in bookings:
            try:
                text = (
                    f"⏰ Напоминание!\n\n"
                    f"Через {minutes} минут у вас занятие:\n"
                    f"📚 {escape_html(booking.get('subject_name', '—'))}\n"
                    f"📅 {booking.get('date', '')}\n"
                    f"🕐 {booking.get('start_time', '')[:5]}\n\n"
                    f"Ждём вас!"
                )
                await bot.send_message(booking["student_user_id"], text)
                # ИСПРАВЛЕНО: помечаем конкретное напоминание (60/15 мин),
                # чтобы не блокировать остальные
                await db.mark_reminder_sent(booking["id"], minutes)
                # Также уведомляем репетитора
                for admin_id in config.ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"⏰ Через {minutes} мин занятие:\n"
                            f"👤 {escape_html(booking.get('full_name', '—'))}\n"
                            f"📚 {escape_html(booking.get('subject_name', '—'))}\n"
                            f"🕐 {booking.get('start_time', '')[:5]}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"[send_booking_reminders] Failed to notify admin {admin_id}: {e}"
                        )
            except Exception as e:
                logger.error(
                    f"[send_booking_reminders] Failed for booking {booking.get('id')}: {e}"
                )
async def send_review_requests(bot: Bot):
    """Отправляет запросы на отзыв после завершённых пробных занятий."""
    today = date.today().isoformat()
    # Упрощённая логика — в реальном проекте нужно отслеживать отправленные запросы
    pass
async def send_payment_reminders(bot: Bot):
    """Напоминания об оплате.
    
    ИСПРАВЛЕНО: логируем ошибки вместо silent pass.
    """
    try:
        payments = await db.get_pending_payments()
    except Exception as e:
        logger.error(f"[send_payment_reminders] Failed to get pending payments: {e}")
        return
    for p in payments:
        # Напоминаем раз в 3 дня, макс 3 раза
        if p.get("reminder_count", 0) >= 3:
            continue
        last_reminder = p.get("last_reminder")
        if last_reminder:
            try:
                last = datetime.fromisoformat(last_reminder)
                if (datetime.now() - last).days < 3:
                    continue
            except (ValueError, TypeError):
                pass
        try:
            await bot.send_message(
                p["student_id"],
                f"💳 <b>Напоминание об оплате</b>\n\n"
                f"Сумма: {p['amount']}₽\n"
                f"Описание: {escape_html(p.get('description', ''))}\n\n"
                f"Пожалуйста, оплатите занятие."
            )
            # Обновляем счётчик напоминаний
            await db.db.execute(
                """UPDATE payments 
                   SET reminder_count = reminder_count + 1, 
                       last_reminder = datetime('now')
                   WHERE id = ?""",
                (p["id"],)
            )
            await db.db.commit()
        except Exception as e:
            logger.error(
                f"[send_payment_reminders] Failed for payment {p.get('id')}: {e}"
            )
async def send_morning_summary(bot: Bot):
    """Отправляет утреннюю сводку администратору.
    
    ИСПРАВЛЕНО: логируем ошибки вместо silent pass.
    """
    today = date.today()
    today_str = today.isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    try:
        bookings_today = await db.get_today_bookings()
    except Exception as e:
        logger.error(f"[send_morning_summary] Failed to get bookings: {e}")
        bookings_today = []
    # Формируем список занятий
    bookings_list = ""
    if bookings_today:
        for b in bookings_today:
            bookings_list += (
                f"  🕐 {b.get('start_time', '')[:5]} — "
                f"{escape_html(b.get('full_name', '—'))} "
                f"({escape_html(b.get('subject_name', '—'))})\n"
            )
    else:
        bookings_list = "  📭 Занятий нет"
    try:
        stats = await db.get_dashboard_stats()
    except Exception as e:
        logger.error(f"[send_morning_summary] Failed to get stats: {e}")
        stats = {}
    text = (
        f"☀️ Доброе утро!\n\n"
        f"📅 Сегодня {format_date(today_str)}\n\n"
        f"📊 Заявок вчера: {stats.get('new_students_month', 0)}\n"
        f"📅 Занятий сегодня: {len(bookings_today)}\n\n"
        f"{bookings_list}\n"
        f"Хорошего продуктивного дня! 🚀"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.error(f"[send_morning_summary] Failed for admin {admin_id}: {e}")
async def send_post_trial_review_request(bot: Bot, booking_id: int):
    """Запрос отзыва после пробного занятия."""
    try:
        booking = await db.get_booking(booking_id)
    except Exception as e:
        logger.error(f"[send_post_trial_review_request] Failed: {e}")
        return
    if not booking:
        return
    try:
        await bot.send_message(
            booking["student_id"],
            Texts.REVIEW_REQUEST,
            reply_markup=rating_keyboard()
        )
    except Exception as e:
        logger.error(f"[send_post_trial_review_request] Failed to send to student: {e}")


async def send_homework_deadline_reminders(bot: Bot):
    """Ежедневное напоминание ученикам: ДЗ сдаётся завтра.

    Приходит по каждому невыполненному заданию с дедлайном «завтра»
    (status='assigned'). Тексты — без давления, но с дедлайном.
    """
    from datetime import date, timedelta

    try:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        items = await db.get_homework_due(tomorrow)
    except Exception as e:
        logger.error(f"[hw_deadline_reminders] Failed: {e}")
        return
    sent = 0
    for hw in items:
        try:
            title = hw.get("title") or "задание"
            await bot.send_message(
                hw["student_id"],
                f"📝 <b>Дедлайн завтра</b>\n\n"
                f"{escape_html(title[:100])}\n"
                f"📅 Сдать до: {hw.get('due_date')}\n\n"
                f"Успеешь? Если нужна помощь — напиши, разберём вместе.",
            )
            sent += 1
        except Exception as e:
            logger.warning(
                "[hw_deadline_reminders] %s: %s", hw.get("student_id"), e
            )
    if sent:
        logger.info(f"[hw_deadline_reminders] отправлено {sent} напоминаний")


async def send_scheduled_messages(bot: Bot):
    """Отправка отложенных сообщений, время которых наступило."""
    try:
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
        due = await db.get_due_messages(now_iso)
    except Exception as e:
        logger.error(f"[scheduled_messages] {e}")
        return
    for m in due:
        try:
            await bot.send_message(m["student_id"], m["text"])
            await db.mark_message_sent(m["id"])
        except Exception as e:
            logger.warning("[scheduled_messages] %s: %s", m["student_id"], e)
            await db.mark_message_sent(m["id"])  # не зависаем на битом


async def auto_complete_bookings(bot: Bot):
    """Завершение прошедших занятий + запрос отзыва ученику.

    Занятие, чей слот уже закончился, переводится в 'completed';
    ученику один раз предлагается оценить занятие.
    """
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(config.TIMEZONE)
        now = datetime.now(tz)
        today = await db.get_today_bookings()
    except Exception as e:
        logger.error(f"[auto_complete] {e}")
        return
    for b in today:
        try:
            end = b.get("end_time") or ""
            if not end or now.strftime("%H:%M") < end[:5]:
                continue  # ещё идёт
            await db.complete_booking(b["id"])
            if b.get("student_user_id"):
                await bot.send_message(
                    b["student_user_id"],
                    "📚 Занятие закончено — как всё прошло?\n"
                    "Оцени, пожалуйста (это займёт 2 секунды):",
                    reply_markup=rating_keyboard(),
                )
        except Exception as e:
            logger.warning("[auto_complete] booking %s: %s", b.get("id"), e)


async def send_tomorrow_summary(bot: Bot):
    """Репетитору вечером: кто записан на завтра."""
    from datetime import date, timedelta
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(config.TIMEZONE)
        tomorrow = (datetime.now(tz).date() + timedelta(days=1)).isoformat()
        cursor = await db.db.execute(
            """SELECT b.*, ts.start_time, ts.end_time, st.full_name,
                      s.name AS subject_name
               FROM bookings b
               LEFT JOIN time_slots ts ON b.slot_id = ts.id
               LEFT JOIN students st ON b.student_id = st.user_id
               LEFT JOIN subjects s ON b.subject_id = s.id
               WHERE ts.date = ? AND b.status IN ('pending', 'confirmed')
               ORDER BY ts.start_time""",
            (tomorrow,)
        )
        rows = [dict(r) for r in await cursor.fetchall()]
    except Exception as e:
        logger.error(f"[tomorrow_summary] {e}")
        return
    if not rows:
        return
    lines = [
        f"{r['start_time'][:5]}–{r['end_time'][:5]} "
        f"{r.get('full_name') or '—'}"
        + (f" · {r['subject_name']}" if r.get("subject_name") else "")
        for r in rows
    ]
    text = f"📅 <b>Завтра ({tomorrow}) — {len(rows)} занятие(й):</b>\n\n" + "\n".join(lines)
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


async def send_weekly_summary(bot: Bot):
    """Репетитору по понедельникам: итоги недели."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(config.TIMEZONE)
        week_ago = (datetime.now(tz) - timedelta(days=7)).strftime("%Y-%m-%d")
        stats = await db.get_payment_stats(period_days=7)
        cursor = await db.db.execute(
            """SELECT COUNT(*) AS n FROM students
               WHERE substr(registration_date, 1, 10) >= ?""",
            (week_ago,)
        )
        new_students = (await cursor.fetchone())["n"]
        cursor = await db.db.execute(
            "SELECT COUNT(*) AS n FROM homework"
            " WHERE substr(COALESCE(submitted_at, created_at), 1, 10) >= ?",
            (week_ago,)
        )
        hw_submitted = (await cursor.fetchone())["n"]
    except Exception as e:
        logger.error(f"[weekly_summary] {e}")
        return
    text = (
        "📈 <b>Итоги недели</b>\n\n"
        f"💵 Оплачено за 7 дней: {stats.get('total_paid', 0):.0f} ₽\n"
        f"⏳ Ожидает оплаты: {stats.get('total_pending', 0):.0f} ₽\n"
        f"👤 Новых учеников: {new_students}\n"
        f"📤 Сдано ДЗ за неделю: {hw_submitted}\n\n"
        f"Хорошей недели!"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass
