"""Утилиты безопасности: хэширование и проверка паролей администратора.

Приоритет — bcrypt (есть в requirements.txt). bcrypt импортируется лениво,
поэтому модуль можно импортировать и без установленных зависимостей
(например, в tests/smoke_test.py, где внешние пакеты подменены шимами).

Если bcrypt недоступен, есть запасной вариант на чистом stdlib — PBKDF2:
    python -c "from utils.security import hash_password_pbkdf2 as h; print(h('ПАРОЛЬ'))"
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)

_BCRYPT_ROUNDS = 12


def _bcrypt():
    """Ленивый импорт bcrypt (чтобы модуль работал и без зависимостей)."""
    try:
        import bcrypt  # type: ignore

        return bcrypt
    except ImportError:
        return None


def hash_password(password: str, *, rounds: int = _BCRYPT_ROUNDS) -> str:
    """Возвращает bcrypt-хэш пароля — значение для ADMIN_PASSWORD_HASH."""
    bcrypt = _bcrypt()
    if bcrypt is None:
        raise RuntimeError(
            "bcrypt не установлен. Выполните: pip install bcrypt\n"
            "…или используйте stdlib-вариант: hash_password_pbkdf2()"
        )
    if not password or len(password) < 8:
        raise ValueError("Пароль должен быть минимум 8 символов.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds)).decode("utf-8")


def verify_password(candidate: str, *, hashed: str) -> bool:
    """Проверяет пароль против хэша ($2b$… bcrypt или pbkdf2$…)."""
    if not candidate or not hashed:
        return False

    if hashed.startswith("$2"):  # bcrypt: $2b$12$...
        bcrypt = _bcrypt()
        if bcrypt is None:
            logger.error(
                "bcrypt не установлен — ADMIN_PASSWORD_HASH невозможно проверить"
            )
            return False
        try:
            return bool(
                bcrypt.checkpw(candidate.encode("utf-8"), hashed.encode("utf-8"))
            )
        except ValueError:
            return False

    if hashed.startswith("pbkdf2$"):
        return _verify_pbkdf2(candidate, hashed)

    logger.error("Неизвестный формат ADMIN_PASSWORD_HASH (ожидается $2b$… или pbkdf2$…)")
    return False


# ---------- PBKDF2-фолбэк без внешних зависимостей ----------

def hash_password_pbkdf2(password: str, *, iterations: int = 600_000) -> str:
    """Хэш на чистом stdlib (hashlib.pbkdf2_hmac, OWASP-рекомендуемые итерации)."""
    if not password or len(password) < 8:
        raise ValueError("Пароль должен быть минимум 8 символов.")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (
        f"pbkdf2${iterations}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    )


def _verify_pbkdf2(candidate: str, stored: str) -> bool:
    try:
        _, iters, salt_b64, dk_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        dk = hashlib.pbkdf2_hmac(
            "sha256", candidate.encode("utf-8"), salt, int(iters)
        )
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False
