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
                    f"🕐 {booking.get('start_time', '')[:5]}\n\n"
                    f"Ждём вас!"
                )
                await bot.send_message(booking["student_user_id"], text)
                await db.mark_reminder_sent(booking["id"])
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
