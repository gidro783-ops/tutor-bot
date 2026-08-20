from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("👥 Ученики", "admin:students"),
        ("📅 Расписание", "admin:schedule"),
        ("📚 Предметы", "admin:subjects"),
        ("📝 Домашние задания", "admin:homework"),
        ("💳 Оплаты", "admin:payments"),
        ("⭐ Отзывы", "admin:reviews"),
        ("📢 Рассылки", "admin:mailings"),
        ("📊 Аналитика", "admin:analytics"),
        ("🔔 Уведомления", "admin:notifications"),
        ("🔕 Режим DND", "admin:dnd"),
        ("🎯 Реферальная система", "admin:referrals"),
        ("🧪 A/B тесты", "admin:ab_tests"),
        ("⚙️ Настройки", "admin:settings"),
        ("🚪 Выйти", "admin:logout"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def admin_students_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📋 Список учеников", "admin:students:list"),
        ("🔍 Поиск ученика", "admin:students:search"),
        ("📊 Статистика учеников", "admin:students:stats"),
        ("📧 Рассылка неактивным", "admin:students:reactivate"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def admin_schedule_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📅 Сегодня", "admin:schedule:today"),
        ("📆 Неделя", "admin:schedule:week"),
        ("➕ Добавить слот", "admin:schedule:add_slot"),
        ("🔄 Повторяющиеся", "admin:schedule:recurring"),
        ("🚫 Заблокировать слот", "admin:schedule:block"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def admin_subjects_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📋 Список предметов", "admin:subjects:list"),
        ("➕ Добавить предмет", "admin:subjects:add"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def admin_homework_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📋 Все ДЗ", "admin:hw:list"),
        ("➕ Задать ДЗ", "admin:hw:add"),
        ("📝 На проверке", "admin:hw:pending"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def admin_payments_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("⏳ Ожидают оплаты", "admin:pay:pending"),
        ("✅ История оплат", "admin:pay:history"),
        ("➕ Создать счёт", "admin:pay:create"),
        ("📊 Статистика", "admin:pay:stats"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def admin_mailings_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📢 Новая рассылка (от бота)", "admin:mail:new"),
        ("👤 Рассылка от моего имени", "admin:mail:userbot"),
        ("📋 Рекламные чаты", "admin:mail:chats"),
        ("➕ Добавить чат", "admin:mail:add_chat"),
        ("📊 Статистика рассылок", "admin:mail:stats"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()

def admin_faq_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📋 Все вопросы", "admin:faq:list"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def admin_analytics_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📊 Воронка", "admin:analytics:funnel"),
        ("📈 По чатам", "admin:analytics:chats"),
        ("💰 Финансы", "admin:analytics:finance"),
        ("👥 Ученики", "admin:analytics:students"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def admin_dnd_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("🔕 Включить DND", "admin:dnd:enable"),
        ("🔔 Выключить DND", "admin:dnd:disable"),
        ("⚙️ Настроить расписание", "admin:dnd:schedule"),
        ("◀️ Назад", "admin:back"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"confirm:{action}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()


def back_button(target: str = "admin:back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data=target)
    return builder.as_markup()


def student_list_keyboard(students: list, page: int = 0,
                          per_page: int = 10) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * per_page
    end = start + per_page
    page_students = students[start:end]

    for s in page_students:
        name = s.get("full_name", "Без имени")
        builder.button(
            text=f"👤 {name}",
            callback_data=f"admin:student:{s['user_id']}"
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(("◀️", f"admin:students:page:{page - 1}"))
    if end < len(students):
        nav_buttons.append(("▶️", f"admin:students:page:{page + 1}"))

    for text, callback in nav_buttons:
        builder.button(text=text, callback_data=callback)

    builder.button(text="◀️ Назад", callback_data="admin:students")
    builder.adjust(1)
    return builder.as_markup()


def student_detail_keyboard(student_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📅 Записи", f"admin:student:{student_id}:bookings"),
        ("📝 ДЗ", f"admin:student:{student_id}:hw"),
        ("💳 Оплаты", f"admin:student:{student_id}:payments"),
        ("✉️ Написать", f"admin:student:{student_id}:message"),
        ("🚫 Деактивировать", f"admin:student:{student_id}:deactivate"),
        ("◀️ Назад", "admin:students:list"),
    ]
    for text, callback in buttons:
        builder.button(text=text, callback_data=callback)
    builder.adjust(2)
    return builder.as_markup()