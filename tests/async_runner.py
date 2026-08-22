# -*- coding: utf-8 -*-
"""Единый event loop для асинхронных тестов.

aiosqlite привязывает соединение к loop'у, на котором оно создано,
поэтому все await-вызовы тестов должны идти через один и тот же loop.
"""
import asyncio

_loop: asyncio.AbstractEventLoop | None = None


def run(coro):
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop.run_until_complete(coro)
