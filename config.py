import hmac
import logging
import os

from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Конфигурация бота. Все секреты — только из переменных окружения (.env)."""

    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]

    # === БЕЗОПАСНОСТЬ: пароль администратора ===
    # Рекомендуется хранить ХЭШ (вариант А):
    #   python -c "from utils.security import hash_password; print(hash_password('ВАШ_ПАРОЛЬ'))"
    # Легаси-вариант ADMIN_PASSWORD (открытый текст) поддерживается для
    # обратной совместимости, но выводит предупреждение при старте.
    _password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    _raw_password = os.getenv("ADMIN_PASSWORD", "")

    if not _password_hash and not _raw_password:
        raise ValueError(
            "Задайте ADMIN_PASSWORD_HASH (рекомендуется) или ADMIN_PASSWORD в .env!\n"
            "  python -c \"from utils.security import hash_password; "
            "print(hash_password('MyStr0ngP@ss2024'))\""
        )

    if _password_hash:
        if not (_password_hash.startswith("$2") or _password_hash.startswith("pbkdf2$")):
            raise ValueError(
                "ADMIN_PASSWORD_HASH должен быть bcrypt-хэшем ($2b$...) "
                "или pbkdf2$-строкой. Сгенерируйте заново через utils.security."
            )
        ADMIN_PASSWORD_HASH: str = _password_hash
        # Открытый пароль в памяти не держим: прямое сравнение == никогда не сработает.
        ADMIN_PASSWORD: str = ""
    else:
        if len(_raw_password) < 8:
            raise ValueError(
                "ADMIN_PASSWORD должен быть минимум 8 символов. "
                "Используйте буквы разного регистра, цифры и спецсимволы."
            )
        logger.warning(
            "⚠️ ADMIN_PASSWORD хранится в .env открытым текстом. "
            "Перейдите на ADMIN_PASSWORD_HASH:\n"
            "  python -c \"from utils.security import hash_password; "
            "print(hash_password('ВАШ_ПАРОЛЬ'))\""
        )
        ADMIN_PASSWORD_HASH = ""
        ADMIN_PASSWORD = _raw_password

    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/tutor_bot.db")

    # Токен платёжного провайдера для оплаты подписки PRO (990 ₽/мес).
    # Получается у @BotFather: /mybots → Payments → подключить провайдера
    # (ЮKassa / Сбер / TELEGRAM —Stars и т.п.) и скопировать токен.
    # Пусто — оплата картой недоступна (остаётся оплата звёздами, см. ниже).
    PAYMENT_PROVIDER_TOKEN: str = os.getenv("PAYMENT_PROVIDER_TOKEN", "")

    # Цена PRO в Telegram Stars (⭐). Звёзды работают БЕЗ платёжного
    # провайдера — оплата доступна сразу. Курс звезды плавает, подберите
    # значение под себя (вывод звёзд — через fragment.com).
    # 0 = отключить оплату звёздами.
    PRO_PRICE_STARS: int = int(os.getenv("PRO_PRICE_STARS", "800"))

    # === ИИ-ассистент (OpenAI-совместимый API) ===
    # Ключ от провайдера. Пусто — ассистент выключен для учеников.
    # Примеры (.env):
    #   DeepSeek:   AI_BASE_URL=https://api.deepseek.com/v1   AI_MODEL=deepseek-chat
    #   OpenAI:     AI_BASE_URL=https://api.openai.com/v1     AI_MODEL=gpt-4o-mini
    #   OpenRouter: AI_BASE_URL=https://openrouter.ai/api/v1  AI_MODEL=любая модель
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "https://api.deepseek.com/v1")
    AI_MODEL: str = os.getenv("AI_MODEL", "deepseek-chat")

    # === БЕЗОПАСНОСТЬ: ключ шифрования ОБЯЗАТЕЛЬНО задавать в .env ===
    # Генерация: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    _raw_key = os.getenv("ENCRYPTION_KEY", "")
    if not _raw_key:
        raise ValueError(
            "ENCRYPTION_KEY must be set in .env! Generate once:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    ENCRYPTION_KEY: str = _raw_key

    # Настраиваемая таймзона
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")
    DND_START: str = os.getenv("DND_START", "09:00")
    DND_END: str = os.getenv("DND_END", "21:00")

    # Настройки пробного занятия
    TRIAL_DURATION_MINUTES: int = 30
    REMINDER_BEFORE_MINUTES: list[int] = [60, 15]  # за час и за 15 минут

    # Настройки рассылки
    MAILING_DELAY_SECONDS: int = 3
    MAX_MAILING_PER_DAY: int = 50

    # Реферальная система
    REFERRAL_BONUS_PERCENT: int = 10

    # Rate limiting для админ-авторизации
    ADMIN_MAX_FAILED_ATTEMPTS: int = int(os.getenv("ADMIN_MAX_FAILED_ATTEMPTS", "5"))
    ADMIN_LOCK_MINUTES: int = int(os.getenv("ADMIN_LOCK_MINUTES", "15"))

    # === Автобэкап базы (services/backup.py) ===
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", "")  # дефолт: <папка БД>/backups
    BACKUP_KEEP: int = int(os.getenv("BACKUP_KEEP", "14"))   # сколько копий хранить
    BACKUP_HOUR: int = int(os.getenv("BACKUP_HOUR", "3"))    # время бэкапа (по TIMEZONE)
    BACKUP_MINUTE: int = int(os.getenv("BACKUP_MINUTE", "30"))

    @classmethod
    def verify_admin_password(cls, candidate: str) -> bool:
        """Единая точка проверки пароля администратора.

        - Режим хэша: bcrypt/pbkdf2 через utils.security (рекомендуется).
        - Легаси-режим: constant-time сравнение через hmac.compare_digest
          (защита от timing-атак, которой нет у обычного ==).
        """
        from utils.security import verify_password

        if cls.ADMIN_PASSWORD_HASH:
            return verify_password(candidate, hashed=cls.ADMIN_PASSWORD_HASH)
        if not candidate or not cls.ADMIN_PASSWORD:
            return False
        return hmac.compare_digest(candidate.encode(), cls.ADMIN_PASSWORD.encode())

    @classmethod
    def get_fernet(cls) -> Fernet:
        return Fernet(cls.ENCRYPTION_KEY.encode())


config = Config()
