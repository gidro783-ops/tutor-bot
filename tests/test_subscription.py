# -*- coding: utf-8 -*-
"""Тесты тарифов: Free/PRO/White Label, триал, лимиты, фичи."""
from datetime import datetime, timedelta

import pytest

from services import subscription as sub


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Служба подписок ходит в config.DATABASE_PATH — уводим во временный файл."""
    from config import config

    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "sub.db"))
    from async_runner import run

    run(sub.init_db())


def run(coro):
    from async_runner import run as _run

    return _run(coro)


OWNER = 1


class TestDefaultState:
    def test_new_tutor_is_free(self):
        s = run(sub.get_subscription(OWNER))
        assert s.plan is sub.Plan.FREE
        assert s.is_active
        assert s.effective_info.max_students == 5

    def test_free_features(self):
        # рассылки и ДЗ на Free доступны, но с лимитами; аналитика закрыта
        assert run(sub.feature_enabled(OWNER, "mailing"))
        assert run(sub.feature_enabled(OWNER, "homework"))
        assert not run(sub.feature_enabled(OWNER, "analytics"))
        assert not run(sub.feature_enabled(OWNER, "white_label"))


class TestTrial:
    def test_trial_grants_pro(self):
        s = run(sub.start_trial(OWNER))
        assert s is not None
        assert s.plan is sub.Plan.PRO
        assert s.is_active
        assert s.effective_info.price_rub == 990
        assert 0 <= s.days_left <= sub.TRIAL_DAYS

    def test_trial_only_once(self):
        assert run(sub.start_trial(OWNER)) is not None
        assert run(sub.start_trial(OWNER)) is None


class TestInvoiceValidation:
    """validate_invoice — проверка счёта до списания денег."""

    def test_rub_ok(self):
        ok, err = sub.validate_invoice("sub:pro", 990 * 100, "RUB")
        assert ok and err == ""

    def test_rub_wrong_amount(self):
        ok, _ = sub.validate_invoice("sub:pro", 100, "RUB")
        assert not ok

    def test_stars_ok(self):
        ok, err = sub.validate_invoice("sub:pro", sub.config.PRO_PRICE_STARS, "XTR")
        assert ok and err == ""

    def test_stars_wrong_amount(self):
        ok, _ = sub.validate_invoice("sub:pro", 1, "XTR")
        assert not ok

    def test_free_rejected(self):
        ok, _ = sub.validate_invoice("sub:free", 0, "RUB")
        assert not ok

    def test_unknown_payload(self):
        for payload in ("", "lesson:42", "sub:unknown"):
            ok, _ = sub.validate_invoice(payload, 100, "RUB")
            assert not ok


class TestQuotas:
    def test_free_mailing_10_per_day(self):
        assert run(sub.mailing_left_today(OWNER)) == 10
        assert run(sub.can_send_mailing(OWNER, 10))
        assert not run(sub.can_send_mailing(OWNER, 11))

        run(sub.consume_mailing(OWNER, 7))
        assert run(sub.mailing_left_today(OWNER)) == 3
        assert not run(sub.can_send_mailing(OWNER, 4))

        run(sub.consume_mailing(OWNER, 3))
        assert run(sub.mailing_left_today(OWNER)) == 0

    def test_free_homework_5_per_month(self):
        assert run(sub.homework_left_this_month(OWNER)) == 5
        for _ in range(5):
            run(sub.consume_homework(OWNER))
        assert run(sub.homework_left_this_month(OWNER)) == 0

    def test_pro_quotas_unlimited(self):
        run(sub.activate(OWNER, sub.Plan.PRO, months=1))
        run(sub.consume_mailing(OWNER, 100))
        run(sub.consume_homework(OWNER))
        assert run(sub.mailing_left_today(OWNER)) is None
        assert run(sub.homework_left_this_month(OWNER)) is None
        assert run(sub.can_send_mailing(OWNER, 10000))


class TestStudentLimit:
    def test_free_allows_five(self):
        for i in range(5):
            assert run(sub.can_add_student(OWNER, i))
        assert not run(sub.can_add_student(OWNER, 5))

    def test_pro_unlimited(self):
        run(sub.activate(OWNER, sub.Plan.PRO, months=1))
        assert run(sub.can_add_student(OWNER, 1000))


class TestActivation:
    def test_activate_pro_month(self):
        s = run(sub.activate(OWNER, sub.Plan.PRO, months=1))
        assert s.plan is sub.Plan.PRO
        assert s.expires_at > datetime.now() + timedelta(days=29)
        assert run(sub.feature_enabled(OWNER, "homework"))
        assert run(sub.feature_enabled(OWNER, "mailing"))

    def test_activation_stacks(self):
        run(sub.activate(OWNER, sub.Plan.PRO, months=1))
        s2 = run(sub.activate(OWNER, sub.Plan.PRO, months=1))
        assert s2.expires_at > datetime.now() + timedelta(days=59)

    def test_expired_pro_downgrades_to_free(self):
        run(sub.activate(OWNER, sub.Plan.PRO, months=1))
        # simulate expiry: сдвигаем expires_at в прошлое напрямую
        import sqlite3

        conn = sqlite3.connect(sub.config.DATABASE_PATH)
        conn.execute(
            "UPDATE subscriptions SET expires_at = ? WHERE tutor_id = ?",
            ((datetime.now() - timedelta(days=1)).isoformat(), OWNER),
        )
        conn.commit()
        conn.close()
        s = run(sub.get_subscription(OWNER))
        assert s.plan is sub.Plan.PRO  # план остаётся, но…
        assert not s.is_active  # …не активен
        assert s.effective_info is sub.PLANS[sub.Plan.FREE]  # эффективный — Free
        assert not run(sub.feature_enabled(OWNER, "analytics"))
        # снова действуют квоты Free
        assert run(sub.mailing_left_today(OWNER)) == 10
        assert run(sub.homework_left_this_month(OWNER)) == 5
