"""Ежедневный автобэкап базы данных.

Решает главный production-риск проекта: на Heroku файловая система
эфемерна, и SQLite-база теряется при каждом рестарте dyno.

- Снапшот делается через SQLite VACUUM INTO — корректно при WAL-режиме
  и не блокирует работающего бота (в отличие от копирования файла).
- Локальная ротация: хранятся последние BACKUP_KEEP копий.
- Копия отправляется администраторам в Telegram — бэкап не умрёт
  вместе с dyno.

Ручной запуск:
    python -m services.backup
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from aiogram import Bot
from aiogram.types import BufferedInputFile

from config import config
from database import db

logger = logging.getLogger(__name__)


def _backup_dir() -> str:
    if config.BACKUP_DIR:
        return config.BACKUP_DIR
    base = os.path.dirname(config.DATABASE_PATH) or "data"
    return os.path.join(base, "backups")


def _rotate(backup_dir: str) -> None:
    """Удаляет старые копии, оставляя BACKUP_KEEP последних."""
    try:
        files = sorted(
            f
            for f in os.listdir(backup_dir)
            if f.startswith("tutor_bot_") and f.endswith(".db")
        )
        for old in files[: max(0, len(files) - config.BACKUP_KEEP)]:
            try:
                os.remove(os.path.join(backup_dir, old))
            except OSError as e:
                logger.warning(f"[backup] Не удалось удалить {old}: {e}")
    except OSError as e:
        logger.warning(f"[backup] Ошибка ротации: {e}")


async def create_local_backup() -> str | None:
    """Создаёт снапшот БД, возвращает путь к файлу (или None при ошибке)."""
    if db.db is None:
        logger.warning("[backup] БД не подключена — пропускаю")
        return None

    backup_dir = _backup_dir()
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"tutor_bot_{stamp}.db")

    # Путь генерируем сами, но на всякий случай экранируем кавычки.
    safe_dest = dest.replace("'", "''")
    try:
        await db.db.execute(f"VACUUM INTO '{safe_dest}'")
    except Exception as e:
        logger.error(f"[backup] VACUUM INTO не удался: {e}")
        return None

    _rotate(backup_dir)
    logger.info(f"[backup] Создана копия: {dest}")
    return dest


async def send_db_backup(bot: Bot) -> None:
    """Создаёт бэкап и отправляет файл всем администраторам в Telegram."""
    path = await create_local_backup()
    if not path:
        return

    try:
        with open(path, "rb") as f:
            payload = f.read()
    except OSError as e:
        logger.error(f"[backup] Не удалось прочитать {path}: {e}")
        return

    size_kb = max(1, len(payload) // 1024)
    caption = (
        "🗄 Ежедневный бэкап базы\n"
        f"📦 {os.path.basename(path)} · {size_kb} КБ\n"
        "Храните файл: файловая система Heroku эфемерна."
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_document(
                admin_id,
                BufferedInputFile(payload, filename=os.path.basename(path)),
                caption=caption,
            )
        except Exception as e:
            logger.warning(f"[backup] Не удалось отправить админу {admin_id}: {e}")


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        await db.connect()
        path = await create_local_backup()
        print(f"✅ Бэкап создан: {path}" if path else "❌ Бэкап не создан (см. логи)")
        await db.close()

    asyncio.run(_main())
