# -*- coding: utf-8 -*-
"""Общее окружение для тестов.

Секреты и путь к БД задаются ДО импорта config/database,
как того требует их инициализация при старте бота.
"""
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

os.environ["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "testpass123")
os.environ["ENCRYPTION_KEY"] = os.environ.get(
    "ENCRYPTION_KEY", "ZmFrZS1rZXktZm9yLXRlc3Rpbmctb25seQ=="
)
os.environ.setdefault("TIMEZONE", "Europe/Moscow")
os.environ["DATABASE_PATH"] = os.path.join(tempfile.gettempdir(), "tbtest_pytest.db")

import pytest  # noqa: E402

from async_runner import run  # noqa: E402
from database import Database  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Свежая база на каждый тест — тесты не влияют друг на друга.

    connect/close и все вызовы тестов идут через один event loop
    (см. async_runner), иначе aiosqlite ломается на смене loop'а.
    """
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    instance = Database()
    run(instance.connect())
    yield instance
    run(instance.close())
