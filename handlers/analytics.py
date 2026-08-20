from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from services.analytics_service import AnalyticsService
from keyboards.admin_kb import back_button
from utils.helpers import escape_html
import logging
logger = logging.getLogger(__name__)
router = Router()
@router.callback_query(F.data == "admin:analytics:funnel")
async def admin_funnel(callback: CallbackQuery):
    """Воронка конверсии (ИСПРАВЛЕНА опечатка funnel→funnel в URL, логика использует funnel)."""
    try:
        report = await AnalyticsService.get_full_report(period_days=30)
        funnel = report.get("funnel", {})
        conv = report.get("conversions", {})
        text = (
            "📊 <b>ВОРОНКА (30 дней):</b>\n\n"
            f"👁 Реклама: {funnel.get('ad_seen', 0)}\n"
            f"▶️ Запуск бота: {funnel.get('bot_started', 0)} ({conv.get('ad_to_start', 0)}%)\n"
            f"📅 Запись на пробное: {funnel.get('trial_booked', 0)} ({conv.get('start_to_trial', 0)}%)\n"
            f"✅ Пришли: {funnel.get('trial_attended', 0)} ({conv.get('trial_to_attend', 0)}%)\n"
            f"🎓 Стали постоянными: {funnel.get('became_regular', 0)} ({conv.get('attend_to_regular', 0)}%)"
        )
        await callback.message.edit_text(
            text,
            reply_markup=back_button("admin:analytics"),
        )
    except Exception as e:
        logger.error(f"Funnel analytics error: {e}")
        await callback.answer("Ошибка загрузки", show_alert=True)
@router.callback_query(F.data == "admin:analytics:finance")
async def admin_finance(callback: CallbackQuery):
    """Финансовая аналитика."""
    try:
        report = await AnalyticsService.get_full_report(period_days=30)
        fin = report.get("finances", {})
        text = (
            "💰 <b>ФИНАНСЫ (30 дней):</b>\n\n"
            f"✅ Получено: {fin.get('total_paid', 0):.0f}₽\n"
            f"⏳ Ожидается: {fin.get('total_pending', 0):.0f}₽"
        )
        await callback.message.edit_text(
            text,
            reply_markup=back_button("admin:analytics"),
        )
    except Exception as e:
        logger.error(f"Finance analytics error: {e}")
        await callback.answer("Ошибка", show_alert=True)
@router.callback_query(F.data == "admin:analytics:chats")
async def admin_chat_analytics(callback: CallbackQuery):
    """Эффективность рекламных чатов."""
    try:
        chat_perf = await db.get_chat_performance()
        if not chat_perf:
            await callback.message.edit_text(
                "📭 Нет данных по чатам.",
                reply_markup=back_button("admin:analytics"),
            )
            return
        text = "📢 <b>Рекламные чаты:</b>\n\n"
        for chat in chat_perf[:10]:
            text += (
                f"💬 {escape_html(chat.get('chat_title', '—'))}: "
                f"{chat.get('total_leads', 0)} лидов\n"
            )
        await callback.message.edit_text(
            text,
            reply_markup=back_button("admin:analytics"),
        )
    except Exception as e:
        logger.error(f"Chat analytics error: {e}")
        await callback.answer("Ошибка", show_alert=True)
@router.callback_query(F.data == "admin:analytics:students")
async def admin_student_analytics(callback: CallbackQuery):
    """Аналитика по ученикам."""
    try:
        stats = await db.get_dashboard_stats()
        text = (
            "👥 <b>Аналитика учеников:</b>\n\n"
            f"📊 Всего: {stats.get('total_students', 0)}\n"
            f"📈 Новых за месяц: {stats.get('new_students_month', 0)}\n"
            f"📅 Записей сегодня: {stats.get('today_bookings', 0)}\n"
            f"🎯 Пробных за месяц: {stats.get('trial_bookings_month', 0)}\n"
            f"📊 Конверсия пробного: {stats.get('trial_conversion', 0)}%\n"
            f"⭐ Средний рейтинг: {stats.get('avg_rating', 0)}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=back_button("admin:analytics"),
        )
    except Exception as e:
        logger.error(f"Student analytics error: {e}")
        await callback.answer("Ошибка", show_alert=True)
