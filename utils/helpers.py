import hashlib
import secrets
import re
from datetime import datetime, date
# ============ СПИСОК ЗАПИСЕЙ УЧЕНИКА ============
def visible_bookings(all_bookings: list) -> list:
    """ИСПРАВЛЕНИЕ: записи, которые ученик видит в «Мои занятия».

    Раньше показывались только 'confirmed', но новые записи создаются
    со статусом 'pending', поэтому у ученика «Мои занятия» был пустым,
    хотя в админ-панели всё видно. Теперь:
    - скрыты только отменённые (cancelled);
    - сначала предстоящие (pending/confirmed, дата >= сегодня) по времени;
    - потом прошедшие/завершённые в обратном порядке.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from config import config
    try:
        today = datetime.now(ZoneInfo(config.TIMEZONE)).date().isoformat()
    except Exception:
        today = date.today().isoformat()

    def sort_key(b):
        return (b.get("date") or "", b.get("start_time") or "")

    active = [b for b in all_bookings if b.get("status") != "cancelled"]
    upcoming = sorted(
        (
            b for b in active
            if b.get("status") in ("pending", "confirmed")
            and (b.get("date") or "") >= today
        ),
        key=sort_key,
    )
    upcoming_ids = {b["id"] for b in upcoming}
    past = sorted(
        (b for b in active if b["id"] not in upcoming_ids),
        key=sort_key,
        reverse=True,
    )
    return upcoming + past
# ============ ЭКРАНИРОВАНИЕ (исправляет Markdown + user input) ============
def escape_html(text: str) -> str:
    """Экранирование HTML-спецсимволов для parse_mode='HTML'."""
    if not text:
        return text or ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
# ============ ФОРМАТИРОВАНИЕ ============
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
    """Вычисление конверсии в процентах (без деления на ноль)."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 1)
# ============ РЕФЕРАЛЬНЫЙ КОД ============
def generate_referral_code(user_id: int) -> str:
    """Генерация уникального реферального кода."""
    data = f"{user_id}:{secrets.token_hex(4)}"
    return hashlib.md5(data.encode()).hexdigest()[:8]
# ============ ОБРЕЗКА ТЕКСТА ============
def truncate_text(text: str, max_length: int = 100) -> str:
    """Обрезка текста с многоточием."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
# ============ ОТМЕНА ВВОДА ============
CANCEL_WORDS = {"отмена", "/cancel", "cancel"}
def is_cancel(text: str) -> bool:
    """Пользователь хочет прервать ввод текстом («отмена», /cancel)."""
    return (text or "").strip().lower() in CANCEL_WORDS
# ============ DND С НАСТРАИВАЕМОЙ ТАЙМЗОНОЙ ============
def is_dnd_active(start_time: str, end_time: str, timezone: str = "Europe/Moscow") -> bool:
    """Проверка, активно ли DND прямо сейчас в заданной таймзоне."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(timezone))
        hours, minutes = now.hour, now.minute
        current_minutes = hours * 60 + minutes
        sh, sm = map(int, start_time.split(":"))
        eh, em = map(int, end_time.split(":"))
        start_minutes = sh * 60 + sm
        end_minutes = eh * 60 + em
        if start_minutes <= end_minutes:
            return start_minutes <= current_minutes < end_minutes
        else:
            return current_minutes >= start_minutes or current_minutes < end_minutes
    except Exception:
        return False
# ============ ВАЛИДАЦИЯ (исправляет отсутствие проверки входных данных) ============
def validate_phone(phone: str) -> str:
    """Валидация номера телефона."""
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
    if not re.match(r'^[\+]?[0-9]{5,20}$', cleaned):
        raise ValueError(
            "Неверный формат телефона. Пример: +79991234567"
        )
    return cleaned
def validate_email(email: str) -> str:
    """Валидация email."""
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise ValueError("Неверный формат email")
    return email
def validate_amount(amount_str: str) -> float:
    """Валидация суммы оплаты."""
    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        raise ValueError("Сумма должна быть числом")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше 0")
    if amount > 1_000_000:
        raise ValueError("Сумма слишком большая (макс 1 000 000)")
    return amount
def validate_date(date_str: str) -> str:
    """Валидация даты в формате YYYY-MM-DD."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Формат даты: YYYY-MM-DD (например 2025-01-15)")
    return date_str
def validate_time(time_str: str) -> str:
    """Валидация времени в формате HH:MM."""
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except (ValueError, AttributeError, IndexError):
        raise ValueError("Формат времени: HH:MM (например 14:30)")
    return time_str
def validate_rating(rating_str: str) -> int:
    """Валидация рейтинга 1-5."""
    try:
        r = int(rating_str)
    except (ValueError, TypeError):
        raise ValueError("Рейтинг должен быть числом от 1 до 5")
    if not 1 <= r <= 5:
        raise ValueError("Рейтинг от 1 до 5")
    return r
def validate_time_range(start: str, end: str) -> None:
    """Проверка что начало раньше конца."""
    if start >= end:
        raise ValueError("Время начала должно быть раньше времени конца")
