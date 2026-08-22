# -*- coding: utf-8 -*-
"""Тесты хэширования пароля админки (bcrypt + PBKDF2-фолбэк)."""
import pytest

from utils.security import (
    hash_password,
    hash_password_pbkdf2,
    verify_password,
)


class TestBcrypt:
    def test_roundtrip(self):
        hashed = hash_password("MyStr0ngP@ss2024")
        assert hashed.startswith("$2")
        assert verify_password("MyStr0ngP@ss2024", hashed=hashed)
        assert not verify_password("wrong-password", hashed=hashed)

    def test_unique_salts(self):
        assert hash_password("same-password-1") != hash_password("same-password-1")

    def test_short_password_rejected(self):
        with pytest.raises(ValueError):
            hash_password("short")

    def test_empty_password_rejected(self):
        with pytest.raises(ValueError):
            hash_password("")


class TestPbkdf2Fallback:
    def test_roundtrip(self):
        hashed = hash_password_pbkdf2("fallback-pass-123")
        assert hashed.startswith("pbkdf2$")
        assert verify_password("fallback-pass-123", hashed=hashed)
        assert not verify_password("other-pass-12345", hashed=hashed)


class TestVerifyEdgeCases:
    def test_empty_inputs(self):
        assert not verify_password("", hashed="")
        assert not verify_password("x", hashed="")

    def test_unknown_hash_format(self):
        # неизвестный формат не должен падать и не должен пускать
        assert not verify_password("whatever-123", hashed="md5$abc$def")

    def test_corrupted_pbkdf2(self):
        assert not verify_password("whatever-123", hashed="pbkdf2$not$a$hash")
