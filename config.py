import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()


class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "tutor_bot.db")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
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

    @classmethod
    def get_fernet(cls) -> Fernet:
        return Fernet(cls.ENCRYPTION_KEY.encode())


config = Config()