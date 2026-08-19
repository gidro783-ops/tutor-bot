from database import db
from utils.helpers import calculate_conversion


class AnalyticsService:
    """Сервис расширенной аналитики."""

    @staticmethod
    async def get_full_report(period_days: int = 30) -> dict:
        """Полный отчёт по всем метрикам."""
        report = {}

        # Основная статистика
        report["dashboard"] = await db.get_dashboard_stats()

        # Воронка
        report["funnel"] = await db.get_funnel_stats(period_days)

        # Эффективность чатов
        report["chat_performance"] = await db.get_chat_performance()

        # Финансы
        report["finances"] = await db.get_payment_stats(period_days)

        # Средний рейтинг
        report["avg_rating"] = await db.get_average_rating()

        # Вычисляем конверсии
        funnel = report["funnel"]
        report["conversions"] = {
            "ad_to_start": calculate_conversion(
                funnel.get("bot_started", 0),
                funnel.get("ad_seen", 0)
            ),
            "start_to_trial": calculate_conversion(
                funnel.get("trial_booked", 0),
                funnel.get("bot_started", 0)
            ),
            "trial_to_attend": calculate_conversion(
                funnel.get("trial_attended", 0),
                funnel.get("trial_booked", 0)
            ),
            "attend_to_regular": calculate_conversion(
                funnel.get("became_regular", 0),
                funnel.get("trial_attended", 0)
            ),
        }

        return report

    @staticmethod
    async def format_report(report: dict) -> str:
        """Форматирование отчёта в текст."""
        text = "📊 **ПОЛНЫЙ ОТЧЁТ**\n\n"

        d = report.get("dashboard", {})
        text += (
            f"👥 Учеников: {d.get('total_students', 0)}\n"
            f"📈 Новых за месяц: {d.get('new_students_month', 0)}\n"
            f"⭐ Рейтинг: {report.get('avg_rating', 0)}\n\n"
        )

        text += "📊 **ВОРОНКА:**\n"
        funnel = report.get("funnel", {})
        conv = report.get("conversions", {})
        text += (
            f"  👁 Реклама: {funnel.get('ad_seen', 0)}\n"
            f"  ▶️ Запуск: {funnel.get('bot_started', 0)} "
            f"({conv.get('ad_to_start', 0)}%)\n"
            f"  📅 Записались: {funnel.get('trial_booked', 0)} "
            f"({conv.get('start_to_trial', 0)}%)\n"
            f"  ✅ Пришли: {funnel.get('trial_attended', 0)} "
            f"({conv.get('trial_to_attend', 0)}%)\n"
            f"  🎓 Постоянные: {funnel.get('became_regular', 0)} "
            f"({conv.get('attend_to_regular', 0)}%)\n\n"
        )

        fin = report.get("finances", {})
        text += (
            f"💰 **ФИНАНСЫ (30 дней):**\n"
            f"  ✅ Получено: {fin.get('total_paid', 0):.0f}₽\n"
            f"  ⏳ Ожидается: {fin.get('total_pending', 0):.0f}₽\n"
        )

        return text