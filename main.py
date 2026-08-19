import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import config
from database import db
from services.scheduler import BotScheduler
from middlewares.auth import DndMiddleware, ActivityMiddleware

from handlers import (
    admin_router,
    student_router,
    booking_router,
    homework_router,
    payments_router,
    reviews_router,
    analytics_router,
    mailing_router,
    referral_router,
)


async def on_startup(bot: Bot):
    """Действия при запуске бота."""
    await db.connect()
    logging.info("✅ База данных подключена")

    # Уведомляем админов
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "🟢 Бот запущен и готов к работе!\n"
                "Используйте /admin для входа в панель управления."
            )
        except Exception:
            pass

    logging.info("✅ Бот запущен")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота."""
    await db.close()
    logging.info("🔴 Бот остановлен")

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🔴 Бот остановлен.")
        except Exception:
            pass


async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )

    # Создаём бота
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Создаём диспетчер
    dp = Dispatcher()

    # Регистрируем мидлвары
    dp.message.middleware(ActivityMiddleware())
    dp.message.middleware(DndMiddleware())

    # Регистрируем роутеры (порядок важен!)
    dp.include_router(admin_router)      # Админ — первым
    dp.include_router(booking_router)    # Запись
    dp.include_router(homework_router)   # ДЗ
    dp.include_router(payments_router)   # Оплаты
    dp.include_router(reviews_router)    # Отзывы
    dp.include_router(analytics_router)  # Аналитика
    dp.include_router(mailing_router)    # Рассылки
    dp.include_router(referral_router)   # Рефералы
    dp.include_router(student_router)    # Студент — последним (catch-all)

    # Регистрируем хуки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запускаем планировщик задач
    scheduler = BotScheduler(bot)
    scheduler.start()

    try:
        # Запускаем бота
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
    finally:
        scheduler.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())