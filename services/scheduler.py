from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot

from services.notification import (
    send_booking_reminders,
    send_morning_summary,
    send_payment_reminders
)
from database import db


class BotScheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    def start(self):
        # Проверка напоминаний каждые 5 минут
        self.scheduler.add_job(
            send_booking_reminders,
            trigger=IntervalTrigger(minutes=5),
            args=[self.bot],
            id="booking_reminders",
            replace_existing=True
        )

        # Утренняя сводка в 8:00
        self.scheduler.add_job(
            send_morning_summary,
            trigger=CronTrigger(hour=8, minute=0),
            args=[self.bot],
            id="morning_summary",
            replace_existing=True
        )

        # Напоминания об оплате в 10:00
        self.scheduler.add_job(
            send_payment_reminders,
            trigger=CronTrigger(hour=10, minute=0),
            args=[self.bot],
            id="payment_reminders",
            replace_existing=True
        )

        # Генерация повторяющихся слотов ежедневно в 00:05
        self.scheduler.add_job(
            self._generate_recurring_slots,
            trigger=CronTrigger(hour=0, minute=5),
            id="recurring_slots",
            replace_existing=True
        )

        self.scheduler.start()

    async def _generate_recurring_slots(self):
        """Генерация повторяющихся слотов на 2 недели вперёд."""
        from datetime import date, timedelta

        # Получаем все повторяющиеся шаблоны
        cursor = await db.db.execute(
            "SELECT * FROM time_slots WHERE is_recurring = 1"
        )
        rows = await cursor.fetchall()
        templates = [dict(r) for r in rows]

        today = date.today()
        for template in templates:
            recurring_day = template.get("recurring_day")
            if recurring_day is None:
                continue

            for i in range(14):
                target_date = today + timedelta(days=i)
                if target_date.weekday() == recurring_day:
                    await db.add_time_slot(
                        target_date.isoformat(),
                        template["start_time"],
                        template["end_time"],
                        is_recurring=False,
                        slot_type="auto_generated"
                    )

    def stop(self):
        self.scheduler.shutdown()