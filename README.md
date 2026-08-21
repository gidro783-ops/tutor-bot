# 🤖 tutor-bot

Telegram-бот для репетитора: запись учеников, расписание, домашние задания,
оплаты, отзывы, рассылки, реферальная программа и аналитика — в одном месте.

Стек: **Python 3.11+ · aiogram 3 · SQLite (aiosqlite, WAL) · APScheduler · Telethon**

---

## ✨ Возможности

| Для ученика | Для репетитора (админ-панель `/admin`) |
|---|---|
| Запись на пробное и обычные занятия | Управление учениками, предметами, слотами |
| «📋 Мои занятия» с напоминаниями за 60 и 15 мин | Повторяющиеся слоты (автогенерация на 2 недели) |
| Домашние задания с файлами и сдачей | ДЗ: выдача, проверка, оценки, фидбек |
| Счета и кнопка «✅ Я оплатил» | Подтверждение оплат, напоминания о долгах |
| Отзывы, реферальная скидка | Рассылки (от бота и userbot), DND-режим, аналитика |

## 🚀 Быстрый старт

```bash
git clone https://github.com/gidro783-ops/tutor-bot.git
cd tutor-bot

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt        # или: make install

cp .env.example .env                   # заполните: токен, ID, пароль, ключ шифрования
python main.py                         # или: make run
```

Ключ шифрования генерируется так:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Пароль админки рекомендуется хранить хэшем (`ADMIN_PASSWORD_HASH`):
```bash
python -c "from utils.security import hash_password; print(hash_password('ВАШ_ПАРОЛЬ'))"
```

## 🧪 Тесты и качество

```bash
make test    # смоук-тест: 23 проверки бизнес-логики (без запуска бота)
make lint    # ruff
```

CI (GitHub Actions) прогоняет оба шага на каждый push — см. `.github/workflows/ci.yml`.

## 🗄 Автобэкап базы

Каждую ночь (по умолчанию 03:30, настраивается `BACKUP_HOUR`/`BACKUP_MINUTE`)
бот делает снапшот SQLite через `VACUUM INTO`, хранит последние 14 копий
(`BACKUP_KEEP`) в `data/backups/` и присылает файл админам в Telegram.
На Heroku это критично — файловая система dyno эфемерна.

Ручной бэкап: `make backup`

## 🏗 Структура

```
main.py                  # точка входа: polling + healthcheck-сервер + планировщик
config.py                # конфигурация из .env (с валидацией обязательных секретов)
database.py              # SQLite: схема, авто-миграции, бизнес-логика
handlers/                # роутеры: admin, student, booking, homework, payments, …
keyboards/               # инлайн/reply-клавиатуры
middlewares/             # DND, активность пользователя
services/                # scheduler, notification, backup, userbot, analytics
utils/                   # helpers, texts, security (хэши паролей)
tests/smoke_test.py      # 23 проверки логики без внешних зависимостей
scripts/legacy/          # исторические скрипты-заплатки (не используются)
docs/CLEANUP.md          # как вычистить историю git от бинарного мусора
```

## 🔒 Безопасность

- Все секреты — только в `.env` (в git не попадает, см. `.gitignore`).
- `*.session` (Telethon) полностью исключены из git — этот файл даёт
  полный доступ к аккаунту.
- Пароль админки: bcrypt-хэш + rate-limit (5 попыток → блок на 15 мин).
- ⚠️ Userbot-рассылки от вашего имени нарушают Telegram ToS и ведут к бану
  аккаунта — используйте рассылку от бота.

## ☁️ Деплой

### Railway (рекомендуется, с Volume)

Персистентное хранилище из коробки: `railway.toml` и `.python-version` уже в репо.
Пошагово — **[docs/RAILWAY.md](docs/RAILWAY.md)**: монтируется Volume в `/data`,
туда уходят база, бэкапы и Telethon-сессия (`DATABASE_PATH=/data/tutor_bot.db`,
`USERBOT_SESSION_PATH=/data/tutor_userbot_session`). Данные переживают передеплои.

### Heroku

`Procfile` и healthcheck-сервер уже на месте. Версия Python — в `runtime.txt`.

```bash
heroku config:set BOT_TOKEN=... ADMIN_IDS=... ADMIN_PASSWORD_HASH=... ENCRYPTION_KEY=...
git push heroku main
```

⚠️ У Heroku файловая система эфемерна — спасает ежедневный бэкап в Telegram
(`services/backup.py`), но Volume Railway надёжнее.

## 🗺 Дорожная карта

- [ ] Онлайн-оплата: Telegram Stars / Telegram Payments (ЮKassa)
- [ ] Миграция SQLite → PostgreSQL для multi-worker деплоя
- [ ] Ruff в строгом режиме (убрать `continue-on-error` в CI)

История исправлений вынесена в `CHANGELOG.md` и `README-FIXES.md`.
