# -*- coding: utf-8 -*-
"""Тесты ИИ-автоответов в ЛС: исключения и решение «отвечать или нет»."""
from services.ai_replies import is_excluded, should_auto_reply


class TestIsExcluded:
    def test_by_username(self):
        skip = [{"id": None, "username": "friend"}]
        assert is_excluded(999, "@Friend", skip)      # регистр и @ не важны
        assert not is_excluded(999, "stranger", skip)

    def test_by_id(self):
        skip = [{"id": 123, "username": None}]
        assert is_excluded(123, "anyone", skip)
        assert not is_excluded(456, "anyone", skip)

    def test_empty_list(self):
        assert not is_excluded(1, "x", [])


class TestShouldAutoReply:
    BASE = dict(
        dm_enabled=True,
        ai_configured=True,
        is_private=True,
        sender_is_bot=False,
        text="Сколько стоит занятие?",
        excluded=False,
        cooldown_left=0,
        manual_pause_left=0,
        quota_left=5,
    )

    def test_happy_path(self):
        ok, reason = should_auto_reply(**self.BASE)
        assert ok and reason == "ok"

    def test_disabled(self):
        ok, reason = should_auto_reply(**{**self.BASE, "dm_enabled": False})
        assert not ok and reason == "disabled"

    def test_excluded(self):
        ok, reason = should_auto_reply(**{**self.BASE, "excluded": True})
        assert not ok and reason == "excluded"

    def test_manual_pause_beats_quota(self):
        ok, reason = should_auto_reply(**{**self.BASE, "manual_pause_left": 100})
        assert not ok and reason == "manual_pause"

    def test_cooldown(self):
        ok, reason = should_auto_reply(**{**self.BASE, "cooldown_left": 30})
        assert not ok and reason == "cooldown"

    def test_free_quota_exhausted(self):
        ok, reason = should_auto_reply(**{**self.BASE, "quota_left": 0})
        assert not ok and reason == "quota"

    def test_pro_unlimited_quota(self):
        ok, _ = should_auto_reply(**{**self.BASE, "quota_left": None})
        assert ok

    def test_ignores_bots_commands_and_groups(self):
        for patch in (
            {"sender_is_bot": True},
            {"text": "/start"},
            {"text": "   "},
            {"is_private": False},
            {"ai_configured": False},
        ):
            ok, _ = should_auto_reply(**{**self.BASE, **patch})
            assert not ok, patch
