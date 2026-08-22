# -*- coding: utf-8 -*-
"""Вход в админ-панель, rate limiting, навигация."""
import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import config
from database import db
from keyboards.admin_kb import admin_main_menu
from utils.texts import Texts

logger = logging.getLogger(__name__)
router = Router()

# =================== RATE LIMITING ===================
_failed_attempts: dict[int, int] = {}
_locked_until: dict[int, datetime] = {}
def _is_locked(admin_id: int) -> bool:
    lock = _locked_until.get(admin_id)
    if lock and datetime.now() < lock:
        return True
    if lock and datetime.now() >= lock:
        _failed_attempts[admin_id] = 0
        del _locked_until[admin_id]
    return False

class AdminAuth(StatesGroup):
    waiting_password = State()

# =================== АВТОРИЗАЦИЯ ===================
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer(Texts.ADMIN_NOT_AUTHORIZED)
        await db.log_action(message.from_user.id, "unauthorized_admin_attempt")
        return
    if await db.check_admin_session(message.from_user.id):
        await show_admin_panel(message)
        return
    await state.set_state(AdminAuth.waiting_password)
    await message.answer(Texts.ADMIN_CMD)
@router.message(AdminAuth.waiting_password)
async def process_password(message: Message, state: FSMContext):
    if message.from_user.id not in config.ADMIN_IDS:
        await state.clear()
        return
    try:
        await message.delete()
    except Exception:
        pass
    admin_id = message.from_user.id
    if _is_locked(admin_id):
        lock = _locked_until[admin_id]
        remaining = int((lock - datetime.now()).total_seconds() / 60) + 1
        await message.answer(
            f"🔒 Слишком много попыток. Попробуйте через {remaining} мин."
        )
        return
    if config.verify_admin_password(message.text or ""):
        _failed_attempts[admin_id] = 0
        _locked_until.pop(admin_id, None)
        await db.authenticate_admin(admin_id, hours=12)
        await db.log_action(admin_id, "admin_login")
        await state.clear()
        await message.answer(Texts.ADMIN_SUCCESS)
        await show_admin_panel(message)
    else:
        _failed_attempts[admin_id] = _failed_attempts.get(admin_id, 0) + 1
        remaining = config.ADMIN_MAX_FAILED_ATTEMPTS - _failed_attempts[admin_id]
        if remaining <= 0:
            _locked_until[admin_id] = datetime.now() + timedelta(
                minutes=config.ADMIN_LOCK_MINUTES
            )
            await message.answer(
                f"🔒 Слишком много неверных попыток. "
                f"Аккаунт заблокирован на {config.ADMIN_LOCK_MINUTES} мин."
            )
            await db.log_action(admin_id, "admin_locked_out")
        else:
            await message.answer(
                f"❌ Неверный пароль. Осталось попыток: {remaining}"
            )
            await db.log_action(admin_id, "admin_wrong_password")
async def show_admin_panel(message: Message):
    stats = await db.get_dashboard_stats()
    text = Texts.ADMIN_PANEL.format(**stats)
    await message.answer(text, reply_markup=admin_main_menu())
async def check_admin(callback: CallbackQuery) -> bool:
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer(Texts.ADMIN_NOT_AUTHORIZED, show_alert=True)
        return False
    if not await db.check_admin_session(callback.from_user.id):
        await callback.answer(Texts.ADMIN_SESSION_EXPIRED, show_alert=True)
        return False
    return True
# =================== НАВИГАЦИЯ ===================
@router.callback_query(F.data == "admin:back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.clear()
    stats = await db.get_dashboard_stats()
    text = Texts.ADMIN_PANEL.format(**stats)
    await callback.message.edit_text(text, reply_markup=admin_main_menu())
@router.callback_query(F.data == "admin:logout")
async def admin_logout(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await db.logout_admin(callback.from_user.id)
    await db.log_action(callback.from_user.id, "admin_logout")
    await state.clear()
    await callback.message.edit_text("👋 Вы вышли из админ-панели.")
