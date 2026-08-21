# 🚄 Деплой на Railway с Volume (постоянное хранилище)

## Зачем Volume

Railway пересоздаёт контейнер при каждом деплое — обычная файловая система
обнуляется. Без Volume теряются **вся SQLite-база и Telethon-сессия**.
Volume решает это: монтируем папку `/data`, туда уходит всё живое.

## Шаг за шагом

1. **Запушьте код** (пакет уже добавил `railway.toml` и `.python-version`):
   ```bash
   git add -A && git commit -m "chore: fix-pack 10/10" && git push
   ```

2. **Railway → New Project → Deploy from GitHub Repo** → выберите `tutor-bot`.

3. **Подключите Volume**: сервис → **Settings → Volumes → + New Volume**:
   - Mount Path: `/data`

4. **Переменные окружения**: сервис → **Variables**:
   ```bash
   BOT_TOKEN=1234567890:AA...
   ADMIN_IDS=123456789
   # хэш генерируется локально:
   # python -c "from utils.security import hash_password; print(hash_password('ВАШ_ПАРОЛЬ'))"
   ADMIN_PASSWORD_HASH=$2b$12$...
   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ENCRYPTION_KEY=...
   TIMEZONE=Europe/Moscow

   # === Volume: то, ради чего всё затевалось ===
   DATABASE_PATH=/data/tutor_bot.db
   USERBOT_SESSION_PATH=/data/tutor_userbot_session
   ```
   `PORT` задавать **не нужно** — Railway выдаёт его сам, бот его подхватывает.
   `BACKUP_DIR` тоже не нужен: по умолчанию бэкапы лягут в `/data/backups`
   (рядом с базой) и тоже попадут на Volume.

5. **Deploy**. Nixpacks сам поставит Python 3.12 и зависимости. Healthcheck
   уже настроен в `railway.toml` (`/health` — этот эндпоинт есть в `main.py`).

## Что теперь живёт на Volume (`/data`)

| Путь | Что | Переменная |
|---|---|---|
| `/data/tutor_bot.db` | вся база данных | `DATABASE_PATH` |
| `/data/backups/` | ротация ежедневных копий | `BACKUP_DIR` (опц.) |
| `/data/tutor_userbot_session.session` | Telethon-сессия | `USERBOT_SESSION_PATH` |

Локально ничего не меняется: без этих переменных всё по-прежнему лежит в `./data`.

## Перенос существующей базы на Volume

1. Возьмите свежий бэкап `tutor_bot_*.db` — бот присылает его вам в Telegram
   ежедневно (или скопируйте `data/tutor_bot.db`).
2. Railway → ваш сервис → **Terminal** (веб-шелл) и одной командой:
   ```bash
   echo "<файл в base64>" | base64 -d > /data/tutor_bot.db
   ```
   (`base64 -w0 tutor_bot.db` — Linux/macOS; в PowerShell:
   `[Convert]::ToBase64String([IO.File]::ReadAllBytes("tutor_bot.db"))`)
3. Перезапустите сервис. Либо просто начните с чистой базы — бот сам её создаст.

## Проверка после деплоя

- Логи: `✅ Health server started on port ...` и `✅ Бот запущен`
- Утром: админам приходит файл бэкапа в Telegram (контрольный бэкап вне Railway)
- Передеплой → данные и userbot-сессия на месте (это и есть Volume)
