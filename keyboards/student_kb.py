from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def student_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    buttons = [
        "📅 Записаться на занятие",
        "📋 Мои занятия",
        "📝 Домашние задания",
        "💳 Оплата",
        "❓ FAQ",
        "🎁 Пригласить друга",
        "👤 Мой профиль",
        "📞 Связаться с репетитором",
    ]
    for btn in buttons:
        builder.button(text=btn)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def subject_selection(subjects: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in subjects:
        price = s.get("price_per_hour", 0)
        builder.button(
            text=f"📚 {s['name']} — {price}₽/час",
            callback_data=f"book:subject:{s['id']}"
        )
    builder.button(text="❌ Отмена", callback_data="book:cancel")
    builder.adjust(1)
    return builder.as_markup()


def date_selection(slots: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Группируем слоты по датам
    dates = sorted(set(s["date"] for s in slots))
    from utils.helpers import format_date
    for d in dates[:14]:  # максимум 14 дат
        builder.button(
            text=f"📅 {format_date(d)}",
            callback_data=f"book:date:{d}"
        )
    builder.button(text="◀️ Назад", callback_data="book:back_to_subject")
    builder.adjust(2)
    return builder.as_markup()


def time_selection(slots: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in slots:
        builder.button(
            text=f"🕐 {s['start_time'][:5]} — {s['end_time'][:5]}",
            callback_data=f"book:slot:{s['id']}"
        )
    builder.button(text="◀️ Назад", callback_data="book:back_to_date")
    builder.adjust(2)
    return builder.as_markup()


def booking_confirm() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="book:confirm")
    builder.button(text="❌ Отмена", callback_data="book:cancel")
    builder.adjust(2)
    return builder.as_markup()


def booking_type_selection() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🆓 Пробное занятие", callback_data="book:type:trial")
    builder.button(text="📚 Обычное занятие", callback_data="book:type:regular")
    builder.button(text="❌ Отмена", callback_data="book:cancel")
    builder.adjust(1)
    return builder.as_markup()


def my_bookings_keyboard(bookings: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    from utils.helpers import format_date
    for b in bookings[:10]:
        status_emoji = {"confirmed": "✅", "pending": "⏳",
                        "completed": "📗", "cancelled": "❌"}.get(
            b.get("status", ""), "❔"
        )
        subject = b.get("subject_name", "—")
        date_str = format_date(b.get("date", ""))
        time_str = b.get("start_time", "")[:5]
        builder.button(
            text=f"{status_emoji} {subject} | {date_str} {time_str}",
            callback_data=f"mybooking:{b['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def booking_detail_keyboard(booking_id: int,
                            can_cancel: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_cancel:
        builder.button(text="❌ Отменить", callback_data=f"mybooking:cancel:{booking_id}")
    builder.button(text="◀️ Назад", callback_data="mybookings:list")
    builder.adjust(1)
    return builder.as_markup()


def homework_list_keyboard(homework_list: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hw in homework_list[:10]:
        status_emoji = {
            "assigned": "📝", "submitted": "📤",
            "graded": "✅"
        }.get(hw.get("status", ""), "❔")
        builder.button(
            text=f"{status_emoji} {hw['title'][:30]}",
            callback_data=f"hw:view:{hw['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def hw_detail_keyboard(hw_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "assigned":
        builder.button(text="📤 Сдать ДЗ", callback_data=f"hw:submit:{hw_id}")
    builder.button(text="◀️ Назад", callback_data="hw:list")
    builder.adjust(1)
    return builder.as_markup()


def rating_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text="⭐" * i, callback_data=f"review:rate:{i}")
    builder.adjust(5)
    return builder.as_markup()


def faq_keyboard(faqs: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for faq in faqs[:15]:
        builder.button(
            text=f"❓ {faq['question'][:40]}",
            callback_data=f"faq:view:{faq['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def payment_keyboard(payments: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in payments[:10]:
        builder.button(
            text=f"💳 {p['amount']}₽ — {p.get('description', '')[:20]}",
            callback_data=f"payment:view:{p['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()