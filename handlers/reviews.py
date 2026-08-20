from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards.student_kb import rating_keyboard
from utils.texts import Texts
from utils.helpers import escape_html, validate_rating
import logging
logger = logging.getLogger(__name__)
router = Router()
class ReviewTextFlow(StatesGroup):
    text = State()
# =================== УЧЕНИК: выбор рейтинга ===================
@router.callback_query(F.data.startswith("review:rate:"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    """Ученик ставит рейтинг 1-5."""
    try:
        rating_str = callback.data.split(":")[-1]
        rating = validate_rating(rating_str)
    except ValueError as e:
        await callback.answer(f"❌ {e}", show_alert=True)
        return
    await state.update_data(rating=rating)
    await state.set_state(ReviewTextFlow.text)
    await callback.message.edit_text(
        f"⭐ Вы поставили {rating}/5\n\n"
        f"Напишите отзыв (или отправьте «-» чтобы пропустить):"
    )
@router.message(ReviewTextFlow.text)
async def process_review_text(message: Message, state: FSMContext):
    """Ученик пишет текст отзыва."""
    data = await state.get_data()
    rating = data.get("rating", 0)
    text = message.text if message.text != "-" else ""
    if len(text) > 2000:
        await message.answer("❌ Отзыв слишком длинный (макс 2000 символов):")
        return
    try:
        await db.create_review(
            student_id=message.from_user.id,
            rating=rating,
            text=text
        )
        await state.clear()
        await message.answer(Texts.REVIEW_THANKS.format(rating=rating))
    except Exception as e:
        logger.error(f"Failed to create review: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")
        await state.clear()
# =================== АДМИН: опубликовать отзыв ===================
@router.callback_query(F.data.startswith("admin:review:publish:"))
async def admin_publish_review(callback: CallbackQuery):
    review_id = int(callback.data.split(":")[-1])
    try:
        cursor = await db.db.execute(
            "UPDATE reviews SET is_published = 1 WHERE id = ?",
            (review_id,)
        )
        await db.db.commit()
        if cursor.rowcount == 0:
            await callback.answer("Не найден", show_alert=True)
            return
        await callback.message.edit_text(f"✅ Отзыв #{review_id} опубликован.")
    except Exception as e:
        logger.error(f"Failed to publish review: {e}")
        await callback.answer("Ошибка", show_alert=True)