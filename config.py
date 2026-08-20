import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet
load_dotenv()
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]
    # === БЕЗОПАСНОСТЬ: пароль ОБЯЗАТЕЛЬНО задавать в .env ===
    _raw_password = os.getenv("ADMIN_PASSWORD", "")
    if not _raw_password:
        raise ValueError(
            "ADMIN_PASSWORD must be set in .env! "
            "Example: ADMIN_PASSWORD=MyStr0ngP@ss2024"
        )
    if len(_raw_password) < 8:
        raise ValueError(
            "ADMIN_PASSWORD must be at least 8 characters. "
            "Use uppercase, lowercase, digits and special chars."
        )
    ADMIN_PASSWORD: str = _raw_password
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/tutor_bot.db")
    # === БЕЗОПАСНОСТЬ: ключ шифрования ОБЯЗАТЕЛЬНО задавать в .env ===
    # Генерация: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    _raw_key = os.getenv("ENCRYPTION_KEY", "")
    if not _raw_key:
        raise ValueError(
            "ENCRYPTION_KEY must be set in .env! Generate once:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    ENCRYPTION_KEY: str = _raw_key
    # Настраиваемая таймзона (было захардкожено Europe/Moscow)
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")
    DND_START: str = os.getenv("DND_START", "09:00")
    DND_END: str = os.getenv("DND_END", "21:00")
    # Настройки пробного занятия
    TRIAL_DURATION_MINUTES: int = 30
    REMINDER_BEFORE_MINUTES: list[int] = [60, 15]  # за час и за 15 минут
    # Настройки рассылки
    MAILING_DELAY_SECONDS: int = 3  # задержка между сообщениями
    MAX_MAILING_PER_DAY: int = 50
    # Реферальная система
    REFERRAL_BONUS_PERCENT: int = 10  # скидка за приведённого друга
    # Rate limiting для админ-авторизации
    ADMIN_MAX_FAILED_ATTEMPTS: int = int(os.getenv("ADMIN_MAX_FAILED_ATTEMPTS", "5"))
    ADMIN_LOCK_MINUTES: int = int(os.getenv("ADMIN_LOCK_MINUTES", "15"))
    @classmethod
    def get_fernet(cls) -> Fernet:
        return Fernet(cls.ENCRYPTION_KEY.encode())
config = Config()
