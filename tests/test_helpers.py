# -*- coding: utf-8 -*-
"""Тесты utils/helpers.py — валидация, форматирование, DND-окна."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from utils.helpers import (
    calculate_conversion,
    escape_html,
    format_date,
    format_time,
    generate_referral_code,
    is_dnd_active,
    truncate_text,
    validate_amount,
    validate_email,
    validate_phone,
    visible_bookings,
)


class TestEscapeHtml:
    def test_specials(self):
        assert escape_html('<b>&"') == "&lt;b&gt;&amp;&quot;"

    def test_empty(self):
        assert escape_html("") == ""
        assert escape_html(None) == ""


class TestFormat:
    def test_date_russian(self):
        assert format_date("2026-08-22") == "Сб, 22 августа"

    def test_date_invalid_returned_as_is(self):
        assert format_date("не-дата") == "не-дата"

    def test_time(self):
        assert format_time("14:30:00") == "14:30"
        assert format_time("") == ""

    def test_truncate(self):
        assert truncate_text("x" * 200, 100).endswith("...")
        assert truncate_text("коротко", 100) == "коротко"


class TestConversion:
    def test_simple(self):
        assert calculate_conversion(1, 4) == 25.0

    def test_zero_denominator(self):
        assert calculate_conversion(5, 0) == 0.0


class TestReferralCode:
    def test_format_and_uniqueness(self):
        codes = {generate_referral_code(i) for i in range(100)}
        assert len(codes) == 100
        assert all(len(c) == 8 for c in codes)


class TestValidation:
    def test_amount_ok(self):
        assert validate_amount("1500.50") == 1500.50
        assert validate_amount(" 800 ") == 800.0

    def test_amount_bad(self):
        for bad in ("abc", "0", "-5", "2000000"):
            with pytest.raises(ValueError):
                validate_amount(bad)

    def test_phone_cleanup(self):
        assert validate_phone("+7 (999) 123-45-67") == "+79991234567"

    def test_phone_bad(self):
        with pytest.raises(ValueError):
            validate_phone("8-999-abc")

    def test_email(self):
        assert validate_email("a@b.co") == "a@b.co"
        with pytest.raises(ValueError):
            validate_email("not-an-email")


class TestDndWindow:
    """Окно строится относительно текущего времени — тест детерминирован
    в любой момент суток (включая переход через полночь)."""

    @staticmethod
    def _hm(total_minutes: int) -> str:
        return f"{total_minutes // 60 % 24:02d}:{total_minutes % 60:02d}"

    def test_active_now(self):
        now = datetime.now(ZoneInfo("Europe/Moscow"))
        cur = now.hour * 60 + now.minute
        assert is_dnd_active(self._hm(cur - 30), self._hm(cur + 30))

    def test_inactive_now(self):
        now = datetime.now(ZoneInfo("Europe/Moscow"))
        cur = now.hour * 60 + now.minute
        assert not is_dnd_active(self._hm(cur + 30), self._hm(cur + 60))

    def test_bad_args_safe(self):
        assert not is_dnd_active("не:время", "23:00")


class TestVisibleBookings:
    def _mk(self, id_, date_, status):
        return {
            "id": id_,
            "date": date_,
            "start_time": "10:00",
            "status": status,
        }

    def test_order_and_filtering(self):
        from config import config

        today = datetime.now(ZoneInfo(config.TIMEZONE)).date().isoformat()
        bookings = [
            self._mk(1, today, "cancelled"),      # скрыта всегда
            self._mk(2, today, "pending"),        # предстоящая
            self._mk(3, "2000-01-01", "completed"),  # давно прошедшая
            self._mk(4, today, "confirmed"),      # предстоящая
        ]
        result = visible_bookings(bookings)
        ids = [b["id"] for b in result]
        assert 1 not in ids
        # предстоящие раньше прошедших
        assert ids.index(2) < ids.index(3)
        assert ids.index(4) < ids.index(3)
