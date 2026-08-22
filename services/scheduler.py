import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot

from services.notification import (
    send_booking_reminders,
    send_homework_deadline_reminders,
    send_morning_summary,
    send_payment_reminders,
)
from services.backup import send_db_backup
from database import db
from config import config

logger = logging.getLogger(__name__)


class BotScheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        # Таймзона настраивается через .env (TIMEZONE), без хардкода
        self.scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

    def start(self):
        # Проверка напоминаний каждые 5 минут
        self.scheduler.add_job(
            send_booking_reminders,
            trigger=IntervalTrigger(minutes=5),
            args=[self.bot],
            id="booking_reminders",
            replace_existing=True,
        )
        # Утренняя сводка в 8:00 (в настроенной таймзоне)
        self.scheduler.add_job(
            send_morning_summary,
            trigger=CronTrigger(hour=8, minute=0),
            args=[self.bot],
            id="morning_summary",
            replace_existing=True,
        )
        # Напоминания об оплате в 10:00
        self.scheduler.add_job(
            send_payment_reminders,
            trigger=CronTrigger(hour=10, minute=0),
            args=[self.bot],
            id="payment_reminders",
            replace_existing=True,
        )
        # Дедлайн ДЗ «завтра» — ученикам (час настраивается HW_REMINDER_HOUR)
        self.scheduler.add_job(
            send_homework_deadline_reminders,
            trigger=CronTrigger(hour=config.HW_REMINDER_HOUR, minute=30),
            args=[self.bot],
            id="hw_deadline_reminders",
            replace_existing=True,
        )
        # Генерация повторяющихся слотов ежедневно в 00:05
        self.scheduler.add_job(
            self._generate_recurring_slots,
            trigger=CronTrigger(hour=0, minute=5),
            id="recurring_slots",
            replace_existing=True,
        )
        # НОВОЕ: ежедневный бэкап базы (по умолчанию 03:30, настраивается
        # BACKUP_HOUR/BACKUP_MINUTE в .env). Копия приходит админам в Telegram —
        # данные не потеряются даже на эфемерной ФС Heroku.
        self.scheduler.add_job(
            send_db_backup,
            trigger=CronTrigger(hour=config.BACKUP_HOUR, minute=config.BACKUP_MINUTE),
            args=[self.bot],
            id="db_backup",
            replace_existing=True,
        )
        self.scheduler.start()

    async def _generate_recurring_slots(self):
        """Генерация повторяющихся слотов на 2 недели вперёд.

        Перед вставкой проверяем дубликаты.
        """
        from datetime import date, timedelta

        try:
            cursor = await db.db.execute(
                "SELECT * FROM time_slots WHERE is_recurring = 1"
            )
            rows = await cursor.fetchall()
            templates = [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to get recurring templates: {e}")
            return

        today = date.today()
        added = 0
        for template in templates:
            recurring_day = template.get("recurring_day")
            if recurring_day is None:
                continue
            for i in range(14):
                target_date = today + timedelta(days=i)
                if target_date.weekday() == recurring_day:
                    # Проверяем, нет ли уже слота на эту дату/время
                    try:
                        existing = await db.db.execute(
                            "SELECT id FROM time_slots WHERE date = ? AND start_time = ?",
                            (target_date.isoformat(), template["start_time"]),
                        )
                        if await existing.fetchone():
                            continue  # Уже есть — пропускаем
                        await db.add_time_slot(
                            target_date.isoformat(),
                            template["start_time"],
                            template["end_time"],
                            is_recurring=False,
                            slot_type="auto_generated",
                        )
                        added += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to add recurring slot for {target_date}: {e}"
                        )
        if added > 0:
            logger.info(f"Generated {added} recurring slots")

    def stop(self):
        # wait=False: не блокируем graceful shutdown бота,
        # пока APScheduler дожидается завершения джобов
        self.scheduler.shutdown(wait=False)
