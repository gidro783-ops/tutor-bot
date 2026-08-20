from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from database import db
from config import config
from keyboards.admin_kb import back_button
from utils.helpers import escape_html
import logging
logger = logging.getLogger(__name__)
router = Router()
# =================== УЧЕНИК: реферальная информация ===================
@router.message(F.text == "🎁 Пригласить друга")
async def referral_info(message: Message):
    user_id = message.from_user.id
    stats = await db.get_referral_stats(user_id)
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    await message.answer(
        f"🎁 <b>Ваша реферальная ссылка:</b>\n\n"
        f"{link}\n\n"
        f"Приведите друга и получите скидку {config.REFERRAL_BONUS_PERCENT}%!\n\n"
        f"📊 Приглашено: {stats['total_referrals']}\n"
        f"✅ Активировано: {stats['completed']}"
    )
# =================== АДМИН: применить бонус ===================
@router.callback_query(F.data.startswith("admin:referral:bonus:"))
async def admin_apply_referral_bonus(callback: CallbackQuery):
    referral_id = int(callback.data.split(":")[-1])
    try:
        cursor = await db.db.execute(
            """UPDATE referrals 
               SET bonus_applied = 1, status = 'completed'
               WHERE id = ? AND bonus_applied = 0""",
            (referral_id,)
        )
        await db.db.commit()
        if cursor.rowcount == 0:
            await callback.answer("Бонус уже применён", show_alert=True)
            return
        await callback.message.edit_text(f"✅ Бонус по рефералу #{referral_id} применён!")
    except Exception as e:
        logger.error(f"Failed to apply referral bonus: {e}")
        await callback.answer("Ошибка", show_alert=True)
