# -*- coding: utf-8 -*-
"""Админка: меню рассылок, DND, оплаты, FAQ, аналитика, рефералы,
отзывы, настройки."""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import config
from database import db
from keyboards.admin_kb import (
    admin_dnd_menu,
    admin_faq_menu,
    admin_mailings_menu,
    admin_payments_menu,
    back_button,
)
from services.userbot import userbot
from utils.helpers import escape_html

from .core import check_admin

logger = logging.getLogger(__name__)
router = Router()

# =================== РАССЫЛКИ ===================
@router.callback_query(F.data == "admin:mailings")
async def admin_mailings(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📢 <b>Рассылки</b>",
        reply_markup=admin_mailings_menu(),
    )

# =================== DND ===================
@router.callback_query(F.data == "admin:dnd")
async def admin_dnd(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "🔕 <b>Режим «Не беспокоить»</b>",
        reply_markup=admin_dnd_menu(),
    )
@router.callback_query(F.data == "admin:dnd:enable")
async def admin_dnd_enable(callback: CallbackQuery):
    # ИСПРАВЛЕНО: убрана сломанная конструкция из двух строк, из-за которой
    # кнопка «Включить DND» работала некорректно
    if not await check_admin(callback):
        return
    await db.set_dnd(True)
    start = await db.get_setting("dnd_start", config.DND_START)
    end = await db.get_setting("dnd_end", config.DND_END)
    await callback.message.edit_text(
        f"✅ <b>DND включён.</b>\n\n"
        f"⏰ Окно: {start} — {end} ({config.TIMEZONE})\n"
        f"В это время бот не отвечает ученикам "
        f"и присылает автоответ.",
        reply_markup=admin_dnd_menu(),
    )
@router.callback_query(F.data == "admin:dnd:disable")
async def admin_dnd_disable(callback: CallbackQuery):
    # ИСПРАВЛЕНО: аналогично кнопке включения
    if not await check_admin(callback):
        return
    await db.set_dnd(False)
    await callback.message.edit_text(
        "🔔 <b>DND выключен.</b>\n\nБот снова отвечает ученикам.",
        reply_markup=admin_dnd_menu(),
    )
# =================== ОПЛАТЫ ===================
@router.callback_query(F.data == "admin:payments")
async def admin_payments(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "💳 <b>Оплаты</b>",
        reply_markup=admin_payments_menu(),
    )
# =================== FAQ ===================
@router.callback_query(F.data == "admin:faq")
async def admin_faq(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "❓ <b>FAQ</b>",
        reply_markup=admin_faq_menu(),
    )
# =================== АНАЛИТИКА ===================
@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    try:
        from services.analytics_service import AnalyticsService
        report = await AnalyticsService.get_full_report(period_days=30)
        text = await AnalyticsService.format_report(report)
        await callback.message.edit_text(text, reply_markup=back_button("admin:back"))
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== РЕФЕРАЛЫ ===================
@router.callback_query(F.data == "admin:referrals")
async def admin_referrals(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    try:
        referrals = await db.get_all_referrals()
        if not referrals:
            await callback.message.edit_text(
                "🎁 Рефералов нет.",
                reply_markup=back_button("admin:back"),
            )
            return
        text = f"🎁 <b>Рефералы</b> (скидка {config.REFERRAL_BONUS_PERCENT}%)\n\n"
        for r in referrals[:10]:
            status_emoji = {"pending": "⏳", "completed": "✅", "expired": "⌛"}
            text += (
                f"{status_emoji.get(r['status'], '❔')} "
                f"<code>{r['referral_code']}</code> — {r['status']}\n"
            )
        await callback.message.edit_text(text, reply_markup=back_button("admin:back"))
    except Exception as e:
        logger.error(f"Referral error: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== ОТЗЫВЫ ===================
@router.callback_query(F.data == "admin:reviews")
async def admin_reviews(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    try:
        all_reviews = await db.get_all_reviews()
        if not all_reviews:
            await callback.message.edit_text(
                "⭐ Отзывов нет.",
                reply_markup=back_button("admin:back"),
            )
            return
        avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
        text = f"⭐ <b>Отзывы</b> (средний: {avg:.1f}/5)\n\n"
        for r in all_reviews[:10]:
            text += f"{'⭐' * r['rating']} {escape_html(r.get('text', '')[:50])}\n"
        await callback.message.edit_text(text, reply_markup=back_button("admin:back"))
    except Exception as e:
        logger.error(f"Reviews error: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== НАСТРОЙКИ ===================
@router.callback_query(F.data == "admin:settings")
async def admin_settings(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    ub_status = "✅ Подключен" if userbot.is_connected else "❌ Не подключен"
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🌍 Таймзона: {config.TIMEZONE}\n"
        f"🔕 DND: {config.DND_START}—{config.DND_END}\n"
        f"🔔 Напоминания: за {', '.join(str(m) + ' мин' for m in config.REMINDER_BEFORE_MINUTES)}\n"
        f"📢 Макс. рассылок/день: {config.MAX_MAILING_PER_DAY}\n"
        f"🎁 Реферальная скидка: {config.REFERRAL_BONUS_PERCENT}%\n"
        f"🔒 Rate limit: {config.ADMIN_MAX_FAILED_ATTEMPTS} попыток, "
        f"блок {config.ADMIN_LOCK_MINUTES} мин\n"
        f"👤 Userbot: {ub_status}"
    )
    await callback.message.edit_text(text, reply_markup=back_button("admin:back"))
