import logging

import phonenumbers
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from keyboards.student_kb import student_main_menu, faq_keyboard
from utils.texts import Texts
from utils.helpers import generate_referral_code, escape_html
from config import config
from utils.fsm_guard import FsmGuard

logger = logging.getLogger(__name__)
router = Router()
router.message.middleware(FsmGuard())


class ContactInfo(StatesGroup):
    phone = State()


def normalize_phone(raw: str) -> str | None:
    """Международная валидация номера, формат E.164 (+79991234567)."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        if not raw.startswith("+"):
            digits = "".join(ch for ch in raw if ch.isdigit())
            if not digits:
                return None
            if len(digits) == 11 and digits.startswith("8"):
                raw = "+7" + digits[1:]
            else:
                raw = "+" + digits
        parsed = phonenumbers.parse(raw, None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None
    except Exception as e:
        logger.warning("Phone parse error: %s", e)
    return None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    args = message.text.split(" ", 1)
    existing_student = await db.get_student(user.id)
    is_new_student = existing_student is None
    referrer_id = None
    source = "direct"
    source_chat_id = None

    if len(args) > 1:
        param = args[1]
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.replace("ref_", ""))
                source = "referral"
            except ValueError:
                pass
        elif param.startswith("chat_"):
            try:
                source_chat_id = int(param.replace("chat_", ""))
                source = "ad_chat"
                await db.increment_chat_leads(source_chat_id)
                await db.log_funnel_event(
                    user.id, "bot_started", source="ad_chat",
                    source_chat_id=source_chat_id
                )
            except ValueError:
                pass

    await db.add_student(
        user_id=user.id,
        full_name=user.full_name or "Без имени",
        username=user.username,
        source=source,
        source_chat_id=source_chat_id,
        referrer_id=referrer_id
    )
    await db.log_funnel_event(user.id, "bot_started", source=source)

    if referrer_id and is_new_student and referrer_id != user.id:
        ref_code = generate_referral_code(user.id)
        is_new_referral = await db.create_referral(referrer_id, user.id, ref_code)
        if is_new_referral:
            referrer = await db.get_student(referrer_id)
            if referrer:
                text = Texts.WELCOME_REFERRAL.format(
                    name=escape_html(user.first_name),
                    referrer=escape_html(referrer["full_name"]),
                    bonus=config.REFERRAL_BONUS_PERCENT
                )
            else:
                text = Texts.WELCOME.format(name=escape_html(user.first_name))
        else:
            text = Texts.WELCOME.format(name=escape_html(user.first_name))
    else:
        text = Texts.WELCOME.format(name=escape_html(user.first_name))

    await state.clear()
    await message.answer(text, reply_markup=student_main_menu())


@router.message(F.text == "📅 Записаться на занятие")
async def book_lesson(message: Message, state: FSMContext):
    from handlers.booking import start_booking
    await start_booking(message, state)


@router.message(F.text == "📋 Мои занятия")
async def my_lessons(message: Message):
    from utils.helpers import visible_bookings
    all_bookings = await db.get_student_bookings(message.from_user.id)
    bookings = visible_bookings(all_bookings)
    if not bookings:
        await message.answer(
            "📭 У вас пока нет записей.\n\n"
            "Нажмите «📅 Записаться на занятие», чтобы выбрать время."
        )
        return
    from keyboards.student_kb import my_bookings_keyboard
    await message.answer(
        "📋 Ваши занятия:\n\n"
        "⏳ — ожидает подтверждения, ✅ — подтверждено",
        reply_markup=my_bookings_keyboard(bookings),
    )


@router.message(F.text == "📝 Домашние задания")
async def my_homework(message: Message):
    hw_list = await db.get_student_homework(message.from_user.id)
    if not hw_list:
        await message.answer("📭 Домашних заданий пока нет.")
        return
    from keyboards.student_kb import homework_list_keyboard
    await message.answer("📝 Ваши задания:", reply_markup=homework_list_keyboard(hw_list))


@router.message(F.text == "💳 Оплата")
async def my_payments(message: Message):
    payments = await db.get_pending_payments(message.from_user.id)
    if not payments:
        await message.answer("✅ Нет неоплаченных счетов!")
        return
    text = "💳 Неоплаченные счета:\n\n"
    for p in payments:
        text += f"• {p['amount']}₽ — {escape_html(p.get('description', ''))}\n"
    await message.answer(text)


@router.message(F.text == "❓ FAQ")
async def show_faq(message: Message):
    faqs = await db.get_all_faq()
    if not faqs:
        await message.answer(
            "❓ Раздел FAQ пока пуст.\n"
            "Напишите ваш вопрос — репетитор ответит лично!"
        )
        return
    await message.answer(
        "❓ Частые вопросы:\n\nВыберите интересующий вопрос:",
        reply_markup=faq_keyboard(faqs),
    )


@router.callback_query(F.data.startswith("faq:view:"))
async def view_faq(callback: CallbackQuery):
    faq_id = int(callback.data.split(":")[-1])
    faqs = await db.get_all_faq()
    faq = next((f for f in faqs if f["id"] == faq_id), None)
    if faq:
        await callback.message.edit_text(
            f"❓ {escape_html(faq['question'])}\n\n{escape_html(faq['answer'])}",
            reply_markup=faq_keyboard(faqs),
        )


@router.message(F.text == "🎁 Пригласить друга")
async def referral_info(message: Message):
    user_id = message.from_user.id
    stats = await db.get_referral_stats(user_id)
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    await message.answer(
        Texts.REFERRAL_INFO.format(
            link=link, bonus=config.REFERRAL_BONUS_PERCENT,
            total=stats["total_referrals"], completed=stats["completed"]
        )
    )


@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message):
    student = await db.get_student(message.from_user.id)
    if not student:
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start")
        return
    bookings = await db.get_student_bookings(message.from_user.id)
    total = len(bookings)
    completed = len([b for b in bookings if b["status"] == "completed"])
    username = student.get("username") or "—"
    text = (
        f"👤 Ваш профиль\n\n"
        f"📛 Имя: {escape_html(student['full_name'])}\n"
        f"📱 Username: @{escape_html(username)}\n"
        f"📞 Телефон: {escape_html(student.get('phone') or 'Не указан')}\n"
        f"📅 Зарегистрирован: {student['registration_date'][:10]}\n"
        f"📊 Всего записей: {total}\n"
        f"✅ Проведено занятий: {completed}\n"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    phone_btn = "📞 Изменить телефон" if student.get("phone") else "📞 Указать телефон"
    builder.button(text=phone_btn, callback_data="profile:phone")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "profile:phone")
async def set_phone(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ContactInfo.phone)
    await callback.message.edit_text(
        "📞 Введите номер телефона с кодом страны, например:\n"
        "+79991234567 или +15551234567"
    )


@router.message(ContactInfo.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = normalize_phone(message.text)
    if phone is None:
        await message.answer(
            "❌ Не похоже на действующий номер телефона.\n"
            "Пришлите номер с кодом страны (+79991234567 или +15551234567):"
        )
        return
    await db.update_student(message.from_user.id, phone=phone)
    await state.clear()
    await message.answer(f"✅ Телефон сохранён: {phone}")
    await my_profile(message)


@router.message(F.text == "📞 Связаться с репетитором")
async def contact_tutor(message: Message):
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"📞 Ученик {escape_html(message.from_user.full_name)} "
                f"(@{escape_html(message.from_user.username or '—')}) хочет связаться."
            )
        except Exception as e:
            logger.error("[contact_tutor] Failed to notify admin %s: %s", admin_id, e)
    await message.answer(
        "✅ Репетитор получил уведомление. С вами свяжутся в ближайшее время!"
    )
