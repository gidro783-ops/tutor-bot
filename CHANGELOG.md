# Changelog

## [10/10 fix-pack] — аудит и усиление

Пакет исправлений по результатам код-ревью. Ничего не ломает: боевая логика
проверена штатным смоук-тестом (23 проверки), обратная совместимость сохранена.

### 🧹 Репозиторий
- Удалён посторонний бинарный архив с **драйвером Realtek WLAN**
  (со стороннего сайта — потенциально опасен) и одноимённая папка.
- `fix_all.py`, `fix2_universal.py` перенесены в `scripts/legacy/` —
  корень проекта чист.
- Инструкция по вычистке истории git: `docs/CLEANUP.md`.

### 🔒 Безопасность
- `.gitignore` теперь исключает `*.session`, `*.session-journal`, `data/backups/`,
  `.env.*` — Telethon-сессия (полный доступ к аккаунту) больше не рискует
  утечь одним `git add .`.
- Добавлен `.env.example` со всеми переменными и генераторами секретов.
- Пароль админки можно хранить **bcrypt-хэшем** (`ADMIN_PASSWORD_HASH`),
  открытый `ADMIN_PASSWORD` поддерживается, но выдаёт предупреждение.
- Вход в админку переведён на `config.verify_admin_password()` —
  constant-time сравнение даже в легаси-режиме (защита от timing-атак).
- Новый модуль `utils/security.py`: bcrypt + stdlib-фолбэк PBKDF2 (600k итераций).

### 🗄 Данные
- Новый `services/backup.py`: ежедневный бэкап БД через `VACUUM INTO`
  (WAL-safe, без остановки бота), ротация последних 14 копий, отправка
  файла админам в Telegram — данные не потеряются на эфемерной ФС Heroku.
- Джоб бэкапа добавлен в `services/scheduler.py` (время — из `.env`).
- `scheduler.stop()` больше не блокирует выключение бота (`wait=False`).
- Ручной бэкап: `make backup` / `python -m services.backup`.

### 🛠 Инженерная культура
- Полноценный `README.md`: быстрый старт, структура, безопасность, деплой.
- GitHub Actions CI: смоук-тест + ruff на каждый push.
- `pyproject.toml` с конфигом ruff и pytest.
- `Makefile`: `install / dev / test / lint / run / backup`.
- `requirements.txt` + `bcrypt`; dev-инструменты вынесены в `requirements-dev.txt`.
- `runtime.txt` фиксирует версию Python для Heroku.

### Совместимость
- Публичный интерфейс `config.py` не изменён — все хэндлеры работают как раньше.
- `tests/smoke_test.py` проходит без правок.
