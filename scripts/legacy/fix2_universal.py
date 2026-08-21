# -*- coding: utf-8 -*-
"""fix2_universal.py — умный патчер: применяет только недостающие правки.
Запуск: python fix2_universal.py  (из папки проекта, где лежит main.py)"""
import os, io, py_compile

OK, SKIP, ERR = "OK", "..", "X"
base = os.path.dirname(os.path.abspath(__file__))

def read(path):
    p = os.path.join(base, path)
    return io.open(p, encoding="utf-8").read() if os.path.exists(p) else None

def write(path, content):
    io.open(os.path.join(base, path), "w", encoding="utf-8").write(content)

def has(path, fragment):
    s = read(path)
    return s is not None and fragment in s

def replace(path, old, new, tag):
    if not os.path.exists(os.path.join(base, path)):
        print(ERR, "файл не найден:", path)
        return False
    src = read(path)
    if new in src:
        print(SKIP, path, "-", tag, "(уже применено)")
        return True
    if old not in src:
        print(ERR, path, "-", tag, "НЕ найдено, правьте вручную")
        return False
    write(path, src.replace(old, new, 1))
    print(OK, path, "-", tag)
    return True

def insert_before(path, marker, insertion, tag, id_mark):
    if has(path, id_mark):
        print(SKIP, path, "-", tag, "(уже применено)")
        return True
    src = read(path)
    if marker not in src:
        print(ERR, path, "-", tag, "маркер не найден")
        return False
    write(path, src.replace(marker, insertion + marker, 1))
    print(OK, path, "-", tag)
    return True

ok = True

print("=" * 60)
print("1) АВТОМИГРАЦИЯ БАЗЫ (лечит «сессия устарела»)")
print("=" * 60)

MIGRATE = '''    async def _migrate(self):
        # Автомиграция: добавляет колонки, которых нет в старой базе
        expected = {
            "students": {
                "phone": "TEXT", "email": "TEXT", "source": "TEXT DEFAULT 'direct'",
                "source_chat_id": "INTEGER", "referrer_id": "INTEGER",
                "is_active": "INTEGER NOT NULL DEFAULT 1", "last_activity": "TEXT",
                "total_lessons": "INTEGER DEFAULT 0", "notes": "TEXT DEFAULT ''",
            },
            "admin_sessions": {
                "auth_time": "TEXT", "session_expires": "TEXT",
                "failed_attempts": "INTEGER DEFAULT 0", "locked_until": "TEXT",
            },
            "time_slots": {
                "is_recurring": "INTEGER NOT NULL DEFAULT 0",
                "recurring_day": "INTEGER",
                "slot_type": "TEXT DEFAULT 'regular'",
                "version": "INTEGER DEFAULT 0",
            },
            "bookings": {
                "subject_id": "INTEGER", "confirmed_at": "TEXT", "cancelled_at": "TEXT",
                "cancel_reason": "TEXT", "reminder_sent": "INTEGER DEFAULT 0",
                "notes": "TEXT DEFAULT ''",
            },
            "homework": {
                "subject_id": "INTEGER", "file_ids": "TEXT DEFAULT '[]'",
                "due_date": "TEXT", "grade": "TEXT", "feedback": "TEXT",
                "submitted_at": "TEXT", "submitted_file_ids": "TEXT DEFAULT '[]'",
            },
            "payments": {
                "payment_method": "TEXT", "paid_at": "TEXT",
                "reminder_count": "INTEGER DEFAULT 0", "last_reminder": "TEXT",
            },
            "reviews": {"booking_id": "INTEGER", "is_published": "INTEGER DEFAULT 0"},
            "mailings": {
                "target_chat_ids": "TEXT DEFAULT '[]'", "sent_at": "TEXT",
                "total_sent": "INTEGER DEFAULT 0", "total_errors": "INTEGER DEFAULT 0",
            },
            "ad_chats": {
                "chat_title": "TEXT DEFAULT ''", "is_active": "INTEGER DEFAULT 1",
                "total_leads": "INTEGER DEFAULT 0", "last_mailing": "TEXT",
            },
            "referrals": {"status": "TEXT DEFAULT 'pending'", "bonus_applied": "INTEGER DEFAULT 0"},
            "funnel_events": {
                "source": "TEXT", "source_chat_id": "INTEGER",
                "metadata": "TEXT DEFAULT '{}'",
            },
        }
        for table, columns in expected.items():
            try:
                cursor = await self.db.execute(f"PRAGMA table_info({table})")
                rows = await cursor.fetchall()
                if not rows:
                    continue
                existing = {r[1] for r in rows}
                for col, decl in columns.items():
                    if col not in existing:
                        try:
                            await self.db.execute(
                                f"ALTER TABLE {table} ADD COLUMN {col} {decl}"
                            )
                            logger.info(f"[migrate] {table}: добавлена колонка {col}")
                        except Exception as e:
                            logger.warning(f"[migrate] {table}.{col}: {e}")
                await self.db.commit()
            except Exception as e:
                logger.warning(f"[migrate] Не удалось проверить {table}: {e}")

'''

if has("database.py", "async def _migrate"):
    print(SKIP, "database.py - миграция уже есть")
else:
    r1 = replace("database.py",
        '        await self.db.execute("PRAGMA foreign_keys=ON")\n        await self._create_tables()',
        '        await self.db.execute("PRAGMA foreign_keys=ON")\n        await self._create_tables()\n        await self._migrate()',
        "вызов _migrate()")
    r2 = insert_before("database.py", "    async def _create_tables(self):", MIGRATE,
        "метод _migrate()", "async def _migrate")
    ok = ok and r1 and r2

print()
print("=" * 60)
print("2) USERBOT: задержка (10 сек ... 2 часа)")
print("=" * 60)

if has("services/userbot.py", "min_delay: float = 5.0"):
    print(SKIP, "services/userbot.py - send_message_safe уже расширен")
    if has("services/userbot.py", "if max_delay > 0:"):
        print(SKIP, "services/userbot.py - тело уже использует min/max_delay")
    else:
        src = read("services/userbot.py")
        src2 = src.replace(
            "            delay = random.uniform(5, 30)\n            await asyncio.sleep(delay)",
            "            if max_delay > 0:\n                delay = random.uniform(min_delay, max_delay)\n                await asyncio.sleep(delay)", 1)
        write("services/userbot.py", src2)
        print(OK, "services/userbot.py - тело использует min/max_delay")
else:
    ok = ok and replace("services/userbot.py",
        "    async def send_message_safe(self, chat_id: int, text: str) -> bool:",
        "    async def send_message_safe(self, chat_id: int, text: str,\n                                min_delay: float = 5.0,\n                                max_delay: float = 30.0) -> bool:",
        "сигнатура send_message_safe")
    ok = ok and replace("services/userbot.py",
        "            delay = random.uniform(5, 30)\n            await asyncio.sleep(delay)",
        "            if max_delay > 0:\n                delay = random.uniform(min_delay, max_delay)\n                await asyncio.sleep(delay)",
        "тело send_message_safe")

ok = ok and replace("services/userbot.py",
    "        for i, chat_id in enumerate(chat_ids):\n            result = await self.send_message_safe(chat_id, text)",
    "        for i, chat_id in enumerate(chat_ids):\n            jitter = min(5.0, delay_between / 4) if delay_between > 0 else 0\n            result = await self.send_message_safe(\n                chat_id, text, min_delay=0, max_delay=jitter\n            )",
    "send_mailing_to_chats jitter")

print()
print("=" * 60)
print("3) ADMIN: выбор задержки в рассылке")
print("=" * 60)

UB_BLOCK = '''UB_DELAYS = [
    ("⚡ 10 сек", 10),
    ("🚶 30 сек", 30),
    ("🕐 1 мин", 60),
    ("🕔 5 мин", 300),
    ("🕝 15 мин", 900),
    ("🕧 30 мин", 1800),
    ("🐢 1 час", 3600),
    ("🐌 2 часа", 7200),
]
def _fmt_delay(sec: int) -> str:
    if sec >= 3600:
        return f"{sec / 3600:g} ч"
    if sec >= 60:
        return f"{sec // 60} мин"
    return f"{sec} сек"
def _fmt_eta(total_sec: int) -> str:
    if total_sec >= 3600:
        return f"~{total_sec / 3600:.1f} ч"
    if total_sec >= 60:
        return f"~{total_sec // 60} мин"
    return f"~{total_sec} сек"
async def _show_delay_choice(callback: CallbackQuery, count: int, mail_text: str):
    builder = InlineKeyboardBuilder()
    for label, sec in UB_DELAYS:
        builder.button(text=label, callback_data=f"ub:delay:{sec}")
    builder.button(text="❌ Отмена", callback_data="ub:mail:cancel")
    builder.adjust(2)
    await callback.message.edit_text(
        f"📢 <b>Рассылка от имени репетитора</b>\\n\\n"
        f"💬 Выбрано чатов: {count}\\n"
        f"📝 Текст: {escape_html(mail_text[:200])}\\n\\n"
        f"⏱ <b>Выберите задержку между сообщениями:</b>\\n"
        f"Чем больше пауза — тем ниже риск бана аккаунта.\\n"
        f"Для безопасности рекомендуется от 15 минут.",
        reply_markup=builder.as_markup(),
    )

'''

UB_CONFIRM = '''@router.callback_query(F.data == "ub:mail:confirm")
async def userbot_mail_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mail_text = data.get("mail_text", "")
    selected = data.get("selected_chats", [])
    if not selected:
        await callback.answer("Выберите хотя бы один чат!", show_alert=True)
        return
    await _show_delay_choice(callback, len(selected), mail_text)


@router.callback_query(F.data.startswith("ub:delay:"))
async def userbot_choose_delay(callback: CallbackQuery, state: FSMContext):
    delay = int(callback.data.split(":")[-1])
    await state.update_data(ub_delay=delay)
    await state.set_state(UserbotMailing.confirm)
    data = await state.get_data()
    mail_text = data.get("mail_text", "")
    selected = data.get("selected_chats", [])
    eta = _fmt_eta(max(0, len(selected) - 1) * delay)
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="ub:mail:send")
    builder.button(text="⏱ Другая задержка", callback_data="ub:mail:confirm")
    builder.button(text="❌ Отмена", callback_data="ub:mail:cancel")
    builder.adjust(1)
    await callback.message.edit_text(
        f"📢 <b>Рассылка от имени репетитора</b>\\n\\n"
        f"💬 Чатов: {len(selected)}\\n"
        f"📝 Текст: {escape_html(mail_text[:300])}\\n"
        f"⏱ Задержка: <b>{_fmt_delay(delay)}</b> между сообщениями\\n"
        f"🕓 Общее время: {eta}\\n\\n"
        f"Подтвердите отправку:",
        reply_markup=builder.as_markup(),
    )'''

admin_src = read("handlers/admin.py")

if admin_src and 'F.data.startswith("ub:delay:")' in admin_src:
    print(SKIP, "handlers/admin.py - выбор задержки уже есть")
else:
    marker = '@router.callback_query(F.data == "ub:mail:confirm")'
    if admin_src and marker in admin_src:
        admin_src = admin_src.replace(marker, UB_BLOCK + UB_CONFIRM + "\n", 1)
        first = admin_src.find(marker)
        second = admin_src.find(marker, first + 10)
        if second != -1:
            end = admin_src.find("@router.", second + 10)
            if end == -1:
                end = admin_src.find("async def", second + 10)
            if end != -1:
                admin_src = admin_src[:second] + admin_src[end:]
        write("handlers/admin.py", admin_src)
        print(OK, "handlers/admin.py - устанавливаем новый ub:mail:confirm с выбором задержки")
    else:
        print(ERR, "handlers/admin.py - не найден ub:mail:confirm")
        ok = False

admin_src = read("handlers/admin.py")
if admin_src and "await _show_delay_choice(callback, len(chat_ids), mail_text)" not in admin_src:
    old_all = '''    await state.update_data(selected_chats=chat_ids)
    await state.set_state(UserbotMailing.confirm)'''
    new_all = '''    await state.update_data(selected_chats=chat_ids)
    await _show_delay_choice(callback, len(chat_ids), mail_text)
    return
    await state.set_state(UserbotMailing.confirm)'''
    if old_all in admin_src:
        write("handlers/admin.py", admin_src.replace(old_all, new_all, 1))
        print(OK, "handlers/admin.py - ub:mail:all теперь спрашивает задержку")
    else:
        print(SKIP, "handlers/admin.py - ub:mail:all (шаблон не найден или уже)")
else:
    print(SKIP, "handlers/admin.py - ub:mail:all уже с задержкой")

admin_src = read("handlers/admin.py")
if admin_src and 'data.get("ub_delay", 30)' not in admin_src:
    old_send = '''    chat_ids = data.get("selected_chats", [])
    await state.clear()'''
    new_send = '''    chat_ids = data.get("selected_chats", [])
    delay = data.get("ub_delay", 30)
    await state.clear()'''
    if old_send in admin_src:
        admin_src = admin_src.replace(old_send, new_send, 1)
        write("handlers/admin.py", admin_src)
        print(OK, "handlers/admin.py - ub:mail:send читает ub_delay")
    else:
        print(ERR, "handlers/admin.py - не найден userbot_mail_send")
        ok = False
else:
    print(SKIP, "handlers/admin.py - ub_delay уже читается")

admin_src = read("handlers/admin.py")
if admin_src and "delay_between=float(delay)" not in admin_src:
    if "delay_between=10.0," in admin_src:
        write("handlers/admin.py", admin_src.replace("delay_between=10.0,", "delay_between=float(delay),", 1))
        print(OK, "handlers/admin.py - delay_between теперь выбранная")
    else:
        print(ERR, "handlers/admin.py - не найдено delay_between=10.0")
        ok = False
else:
    print(SKIP, "handlers/admin.py - delay_between уже выбранная")

print()
print("=" * 60)
print("4) ПРОВЕРКА КОМПИЛЯЦИИ")
print("=" * 60)
for f in ["database.py", "services/userbot.py", "handlers/admin.py"]:
    try:
        py_compile.compile(os.path.join(base, f), doraise=True)
        print(OK, f, "компилируется")
    except Exception as e:
        print(ERR, "ОШИБКА:", f, e)
        ok = False

print()
if ok:
    print("ВСЁ ГОТОВО! Дальше в PowerShell:")
    print("  git add .")
    print("  git commit -m 'fix admin session + userbot delay choice'")
    print("  git push")
    print()
    print("При первом запуске бота в логах будут строки [migrate] - база обновилась.")
else:
    print("ЧАСТЬ НЕ ПРИМЕНИЛАСЬ (X) - пришлите этот вывод, скажу точно, что править вручную.")