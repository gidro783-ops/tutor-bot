import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from services.userbot import userbot
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
    fixes_router,
)
async def healthcheck(request):
    return web.Response(text="OK")
async def start_web_server():
    app = web.Application()
    app.router.add_get("/", healthcheck)
    app.router.add_get("/health", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logging.info(f"✅ Health server started on port {port}")
    return runner
async def notify_admins(bot: Bot, text: str):
    """ИСПРАВЛЕНО: логируем ошибки вместо silent pass."""
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logging.error(f"[notify_admins] Failed to notify admin {admin_id}: {e}")
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    await db.connect()
    # Подключаем userbot (если есть сохраненная сессия)
    try:
        await userbot.connect()
    except Exception as e:
        logging.warning(f"Userbot не подключен: {e}")
    logging.info("✅ База данных подключена")
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.message.middleware(ActivityMiddleware())
    dp.message.middleware(DndMiddleware())
    dp.include_router(admin_router)
    dp.include_router(fixes_router)
    dp.include_router(booking_router)
    dp.include_router(homework_router)
    dp.include_router(payments_router)
    dp.include_router(reviews_router)
    dp.include_router(analytics_router)
    dp.include_router(mailing_router)
    dp.include_router(referral_router)
    dp.include_router(student_router)
    scheduler = BotScheduler(bot)
    web_runner = None
    try:
        web_runner = await start_web_server()
        scheduler.start()
        await notify_admins(
            bot,
            "🟢 Бот запущен и готов к работе!"
        )
        logging.info("✅ Бот запущен")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
    except Exception as e:
        logging.exception(f"❌ Критическая ошибка: {e}")
        raise
    finally:
        try:
            scheduler.stop()
        except Exception as e:
            logging.warning(f"Scheduler stop error: {e}")
        try:
            await notify_admins(bot, "🔴 Бот остановлен.")
        except Exception as e:
            logging.warning(f"Notify admins error: {e}")
        try:
            if web_runner:
                await web_runner.cleanup()
        except Exception as e:
            logging.warning(f"Web runner cleanup error: {e}")
        try:
            await db.close()
        except Exception as e:
            logging.warning(f"DB close error: {e}")
        try:
            await bot.session.close()
        except Exception as e:
            logging.warning(f"Bot session close error: {e}")
if __name__ == "__main__":
    asyncio.run(main())