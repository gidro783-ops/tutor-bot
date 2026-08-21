# -*- coding: utf-8 -*-
"""
Смоук-тест исправлений tutor-bot.
Запуск (без aiogram, без интернет-вызовов, на отдельной тестовой БД):
    python3 tests/smoke_test.py
Проверяет: напоминания, «Мои занятия», двойное бронирование,
оплату «Я оплатил», DND с таймзоной, утреннюю сводку.
"""
import sys, os, asyncio, sqlite3, types
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DB = "/tmp/tbtest_tutor.db"

os.environ["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "testpass123")
os.environ["ENCRYPTION_KEY"] = os.environ.get("ENCRYPTION_KEY", "ZmFrZS1rZXktZm9yLXRlc3Rpbmctb25seQ==")
os.environ.setdefault("TIMEZONE", "Europe/Moscow")
os.environ["DATABASE_PATH"] = TEST_DB
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from zoneinfo import ZoneInfo
TZ = ZoneInfo(os.environ["TIMEZONE"])
print(f"Серверное время      : {datetime.now():%H:%M:%S}")
print(f"Время {os.environ['TIMEZONE']} : {datetime.now(TZ):%H:%M:%S}")

# --- лёгкий shim aiosqlite поверх sqlite3 (чтобы не ставить зависимости) ---
class _Cursor:
    def __init__(self, c): self._c = c
    async def fetchall(self): return self._c.fetchall()
    async def fetchone(self): return self._c.fetchone()
    @property
    def rowcount(self): return self._c.rowcount
    @property
    def lastrowid(self): return self._c.lastrowid

class _Conn:
    def __init__(self, path):
        self._c = sqlite3.connect(path)
        self._rf = None
    @property
    def row_factory(self): return self._rf
    @row_factory.setter
    def row_factory(self, f):
        self._rf = f
        self._c.row_factory = f
    async def execute(self, sql, params=None):
        return _Cursor(self._c.execute(sql) if params is None else self._c.execute(sql, params))
    async def executescript(self, sql): self._c.executescript(sql)
    async def commit(self): self._c.commit()
    async def close(self): self._c.close()

aiosqlite = types.ModuleType("aiosqlite")
aiosqlite.Row = sqlite3.Row
async def _connect(path): return _Conn(path)
aiosqlite.connect = _connect
sys.modules["aiosqlite"] = aiosqlite

dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *a, **k: None
sys.modules["dotenv"] = dotenv
crypto = types.ModuleType("cryptography")
fernet_mod = types.ModuleType("cryptography.fernet")
class Fernet:
    def __init__(self, key): pass
fernet_mod.Fernet = Fernet
crypto.fernet = fernet_mod
sys.modules["cryptography"] = crypto
sys.modules["cryptography.fernet"] = fernet_mod

sys.path.insert(0, BASE)
from database import db  # noqa: E402
from utils.helpers import visible_bookings  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

PASS = 0
def ok(name, cond):
    global PASS
    assert cond, f"FAILED: {name}"
    PASS += 1
    print(f"  ✓ {name}")

async def main():
    await db.connect()
    now = datetime.now(TZ)
    date_str = now.date().isoformat()
    t = lambda dt: dt.strftime("%H:%M")

    await db.add_student(111, "Тест Учеников", username="test_u")
    await db.add_subject("Математика", 1500)
    subj = (await db.get_subjects())[0]

    a_start = now + timedelta(minutes=30)
    await db.add_time_slot(date_str, t(a_start), t(a_start + timedelta(minutes=30)))
    b_start = now + timedelta(minutes=10)
    await db.add_time_slot(date_str, t(b_start), t(b_start + timedelta(minutes=30)))
    slots = await db.get_available_slots()
    slot_a = [s for s in slots if s["date"] == date_str and s["start_time"] == t(a_start)][0]
    slot_b = [s for s in slots if s["date"] == date_str and s["start_time"] == t(b_start)][0]

    print("\n[1] Напоминания (было: не приходили никогда)")
    ba = await db.create_booking(111, slot_a["id"], subj["id"], "trial")
    bb = await db.create_booking(111, slot_b["id"], subj["id"], "regular")
    bkb = await db.get_booking(ba)
    ok("запись создаётся со статусом pending", bkb and bkb["status"] == "pending")
    r60 = await db.get_upcoming_bookings(60)
    ok("pending-записи попадают в окно 60 минут", ba in {b["id"] for b in r60} and bb in {b["id"] for b in r60})
    r15 = await db.get_upcoming_bookings(15)
    ok("в окно 15 минут попадает только ближайшее занятие", bb in {b["id"] for b in r15} and ba not in {b["id"] for b in r15})
    await db.mark_reminder_sent(bb, 60)
    r60b = await db.get_upcoming_bookings(60)
    ok("60-мин напоминание не дублируется", bb not in {b["id"] for b in r60b})
    r15b = await db.get_upcoming_bookings(15)
    ok("15-мин напоминание НЕ заблокировано общим флагом (было: не шло)", bb in {b["id"] for b in r15b})
    await db.mark_reminder_sent(bb, 15)
    r15c = await db.get_upcoming_bookings(15)
    ok("15-мин напоминание отправляется один раз", bb not in {b["id"] for b in r15c})

    print("\n[2] «Мои занятия» (было: пусто, хотя запись есть)")
    vis = visible_bookings(await db.get_student_bookings(111))
    ok("pending-записи видны ученику", {b["id"] for b in vis} == {ba, bb})
    await db.cancel_booking(bb, "тест")
    vis2 = visible_bookings(await db.get_student_bookings(111))
    ok("отменённая запись скрыта", {b["id"] for b in vis2} == {ba})

    print("\n[3] Защита от двойного бронирования слота")
    await db.add_student(222, "Второй Ученик")
    dup = await db.create_booking(222, slot_a["id"], subj["id"], "trial")
    ok("вторую активную запись на занятый слот создать нельзя", dup == 0)

    print("\n[4] Оплата: «Я оплатил» → подтверждение репетитору")
    pid = await db.create_payment(111, 1500, "Занятие по математике")
    p0 = await db.get_payment_by_id(pid)
    ok("в счёте есть имя ученика для уведомления репетитора",
       p0["status"] == "pending" and p0["full_name"] == "Тест Учеников")
    ok("статус становится reported", await db.report_payment_paid(pid))
    p1 = await db.get_payment_by_id(pid)
    ok("повторное нажатие 'Я оплатил' игнорируется",
       p1["status"] == "reported" and not await db.report_payment_paid(pid))
    ok("reported-счёт больше не в 'ожидает оплаты' (конец спама напоминаниями)",
       pid not in {x["id"] for x in await db.get_pending_payments()})
    ok("reported-счёт виден репетитору", pid in {x["id"] for x in await db.get_reported_payments()})
    await db.confirm_payment(pid, method="admin_confirmed")
    ok("репетитор подтвердил → paid", (await db.get_payment_by_id(pid))["status"] == "paid")
    ok("счёт в истории оплат", pid in {x["id"] for x in await db.get_all_payments()})

    print("\n[5] DND: таймзона (было: окно по UTC сервера, DND 'не работал')")
    await db.set_dnd(True)
    await db.set_setting("dnd_start", t(now - timedelta(hours=1)))
    await db.set_setting("dnd_end", t(now + timedelta(hours=1)))
    isd, reply = await db.is_dnd_active()
    ok("DND активен внутри окна (время по .env TIMEZONE)", isd)
    await db.set_setting("dnd_start", t(now + timedelta(hours=2)))
    await db.set_setting("dnd_end", t(now + timedelta(hours=3)))
    isd2, _ = await db.is_dnd_active()
    ok("DND неактивен вне окна", not isd2)

    print("\n[6] Утренняя сводка: pending-записи тоже считаются")
    today = await db.get_today_bookings()
    ok("pending-запись на сегодня в списке 'сегодня'", any(b["id"] == ba for b in today))

    await db.close()
    print(f"\n✅ ВСЕ {PASS} ПРОВЕРОК ПРОЙДЕНО")

asyncio.run(main())
