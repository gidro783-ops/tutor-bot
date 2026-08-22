# -*- coding: utf-8 -*-
"""Админ-панель. Модули подключаются к общему роутеру `router`.

`check_admin` и `show_admin_panel` переэкспортируются для совместимости
(на них ссылаются handlers.fixes и handlers.payments).
"""
from aiogram import Router

from .ai import router as ai_router
from .core import check_admin, show_admin_panel
from .core import router as core_router
from .extra import router as extra_router
from .misc import router as misc_router
from .schedule import router as schedule_router
from .students import router as students_router
from .subjects import router as subjects_router
from .userbot import router as userbot_router

router = Router()
router.include_router(core_router)
router.include_router(students_router)
router.include_router(subjects_router)
router.include_router(schedule_router)
router.include_router(ai_router)
router.include_router(extra_router)
router.include_router(misc_router)
router.include_router(userbot_router)

__all__ = ["router", "check_admin", "show_admin_panel"]
