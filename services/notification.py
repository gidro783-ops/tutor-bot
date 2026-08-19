import asyncio
from datetime import datetime, date, timedelta
from aiogram import Bot

from database import db
from config import config
from utils.texts import Texts
from utils.helpers import format_date
from keyboards.student_kb import rating_keyboard


async def send_booking_reminders(bot: Bot):
    """Отправляет напоминания о предстоящих занятиях."""
    for minutes in config.REMINDER_BEFORE_MINUTES:
        bookings = await db.get_upcoming_bookings(minutes_ahead=minutes)
        for booking in bookings:
            try:
                text = Texts.REMINDER.format(
                    minutes=minutes,
                    subject=booking.get("subject_name", "—"),
                    start_time=booking.get("start_time", "")[:5]
                )
                await bot.send_message(booking["student_user_id"], text)
                await db.mark_reminder_sent(booking["id"])

                # Также уведомляем репетитора
                for admin_id in config.ADMIN_IDS:
                    await bot.send_message(
                        admin_id,
                        f"⏰ Через {minutes} мин занятие:\n"
                        f"👤 {booking.get('full_name', '—')}\n"
                        f"📚 {booking.get('subject_name', '—')}\n"
                        f"🕐 {booking.get('start_time', '')[:5]}"
                    )
            except Exception:
                pass


async def send_review_requests(bot: Bot):
    """Отправляет запросы на отзыв после завершённых пробных занятий."""
    today = date.today().isoformat()
    # Ищем завершённые сегодня пробные занятия
    # Это упрощённая логика — в реальном проекте нужно
    # отслеживать, отправлен ли уже запрос
    pass


async def send_payment_reminders(bot: Bot):
    """Напоминания об оплате."""
    payments = await db.get_pending_payments()
    for p in payments:
        # Напоминаем раз в 3 дня, макс 3 раза
        if p.get("reminder_count", 0) >= 3:
            continue

        last_reminder = p.get("last_reminder")
        if last_reminder:
            last = datetime.fromisoformat(last_reminder)
            if (datetime.now() - last).days < 3:
                continue

        try:
            await bot.send_message(
                p["student_id"],
                Texts.PAYMENT_REMINDER.format(
                    amount=p["amount"],
                    description=p.get("description", "")
                )
            )
        except Exception:
            pass


async def send_morning_summary(bot: Bot):
    """Отправляет утреннюю сводку администратору."""
    today = date.today()
    today_str = today.isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()

    # Заявки вчера
    bookings_today = await db.get_today_bookings()

    # Формируем список занятий
    bookings_list = ""
    if bookings_today:
        for b in bookings_today:
            bookings_list += (
                f"  🕐 {b.get('start_time', '')[:5]} — "
                f"{b.get('full_name', '—')} "
                f"({b.get('subject_name', '—')})\n"
            )
    else:
        bookings_list = "  📭 Занятий нет"

    stats = await db.get_dashboard_stats()

    text = Texts.MORNING_SUMMARY.format(
        date=format_date(today_str),
        yesterday_requests=stats.get("new_students_month", 0),
        today_bookings=len(bookings_today),
        bookings_list=bookings_list
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


async def send_post_trial_review_request(bot: Bot, booking_id: int):
    """Запрос отзыва после пробного занятия."""
    booking = await db.get_booking(booking_id)
    if not booking:
        return

    try:
        await bot.send_message(
            booking["student_id"],
            Texts.REVIEW_REQUEST,
            reply_markup=rating_keyboard()
        )
    except Exception:
        pass