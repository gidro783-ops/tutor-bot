# test_us_code_type.py
# Смотрит, КУДА реально Telegram шлёт код для вашего US-номера.
# Запуск из папки бота (там, где лежит .env):
#     python test_us_code_type.py
# Скрипт сам читает .env — ничего настраивать не нужно.
import asyncio
import os
import sys


def load_env(path=".env"):
    """Простой парсер .env без сторонних библиотек."""
    if not os.path.exists(path):
        return False
    loaded = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
                loaded += 1
    return loaded > 0


try:
    from telethon import TelegramClient
    from telethon.tl import types as tl_types
    from telethon.errors import SessionPasswordNeededError
except ImportError:
    print("НЕТ telethon. Выполните: pip install telethon==1.36.0")
    sys.exit(1)

if load_env():
    print("Файл .env прочитан ✓")
else:
    print("ВНИМАНИЕ: .env не найден рядом со скриптом")

API_ID = int(os.getenv("TELEGRAM_API_ID", "0") or "0")
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
if not API_ID or not API_HASH:
    print("Нет TELEGRAM_API_ID / TELEGRAM_API_HASH. Проверьте .env:")
    print("  TELEGRAM_API_ID=123456")
    print("  TELEGRAM_API_HASH=abcdef...")
    sys.exit(1)
print(f"API_ID загружен: {str(API_ID)[:4]}****")

SESSION = "test_us.session"
if os.path.exists(SESSION):
    os.remove(SESSION)


async def main():
    phone = input("Введите US-номер (например +15551234567): ").strip()
    if not phone.startswith("+"):
        digits = "".join(ch for ch in phone if ch.isdigit())
        phone = "+" + digits
    print(f"Номер: {phone}")
    print("Отправляю код (send_code_request)...")

    client = TelegramClient(
        SESSION, API_ID, API_HASH,
        system_version="4.16.30-vxCUSTOM",
        device_model="Desktop",
        app_version="1.0",
        lang_code="en",
        system_lang_code="en-US",
    )
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
        print()
        print("=== РЕЗУЛЬТАТ — КУДА ШЛЁТ КОД ===")
        print(f"    type    : {type(sent).__name__}")
        print(f"    hash    : {sent.phone_code_hash}")
        print(f"    type obj: {sent.type}")
        print(f"    is App?  {'ДА — код пришёл в приложение Telegram' if isinstance(sent.type, tl_types.auth.SentCodeTypeApp) else 'нет'}")
        print(f"    is SMS?  {'ДА — код пришёл по SMS на телефон' if isinstance(sent.type, tl_types.auth.SentCodeTypeSms) else 'нет'}")
        tname = type(sent.type).__name__
        print(f"    is Call? {'ДА — звонок/флеш-колл' if ('Call' in tname or 'Flash' in tname) else 'нет'}")
        print()
        code = input("Введите код (или просто Enter, чтобы выйти): ").strip()
        if not code:
            print("Выходили без ввода. Пришлите строки выше — поймём причину.")
            return
        print("Пробую sign_in с phone_code_hash...")
        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
            me = await client.get_me()
            print()
            print("=== SUCCESS! ===")
            print(f"    Авторизованы как: {me.first_name} ({me.phone})")
        except SessionPasswordNeededError:
            pwd = input("Нужен 2FA-пароль Telegram. Введите: ").strip()
            await client.sign_in(password=pwd)
            me = await client.get_me()
            print(f"=== SUCCESS (2FA)! {me.first_name} ({me.phone}) ===")
        except Exception as e:
            print()
            print(f"=== ОШИБКА: {type(e).__name__} ===")
            print(f"    Текст: {e}")
    except Exception as e:
        print(f"Ошибка до/при отправке кода: {type(e).__name__}: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        try:
            os.remove(SESSION)
        except Exception:
            pass


asyncio.run(main())
