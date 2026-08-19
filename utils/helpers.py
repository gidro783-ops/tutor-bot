import hashlib
import secrets
from datetime import datetime, date


def generate_referral_code(user_id: int) -> str:
    """Генерация уникального реферального кода."""
    data = f"{user_id}:{secrets.token_hex(4)}"
    return hashlib.md5(data.encode()).hexdigest()[:8]


def format_date(date_str: str) -> str:
    """Форматирование даты для отображения."""
    try:
        d = date.fromisoformat(date_str)
        months = [
            "", "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        day_name = days[d.weekday()]
        return f"{day_name}, {d.day} {months[d.month]}"
    except (ValueError, IndexError):
        return date_str


def format_time(time_str: str) -> str:
    """Форматирование времени."""
    return time_str[:5] if time_str else ""


def calculate_conversion(numerator: int, denominator: int) -> float:
    """Вычисление конверсии в процентах."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 1)


def escape_markdown(text: str) -> str:
    """Экранирование спецсимволов для MarkdownV2."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>',
                     '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def truncate_text(text: str, max_length: int = 100) -> str:
    """Обрезка текста с многоточием."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."