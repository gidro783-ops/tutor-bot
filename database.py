import aiosqlite
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional
import os
from config import config
logger = logging.getLogger(__name__)
class Database:
    def __init__(self):
        # Берём путь из переменной окружения или используем дефолтный
        db_path = os.getenv("DATABASE_PATH", "data/tutor_bot.db")
        
        # Создаём папку если её нет
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
    async def connect(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        await self._migrate()
    async def close(self):
        if self.db:
            await self.db.close()
    async def _migrate(self):
        # Автомиграция: добавляет колонки, которых нет в старой базе
        expected = {
            "students": {
                "phone": "TEXT", "email": "TEXT", "source": "TEXT DEFAULT 'direct'",
                "source_chat_id": "INTEGER", "referrer_id": "INTEGER",
                "is_active": "INTEGER NOT NULL DEFAULT 1", "last_activity": "TEXT",
                "total_lessons": "INTEGER DEFAULT 0", "notes": "TEXT DEFAULT ''",
                "lessons_balance": "INTEGER NOT NULL DEFAULT 0",
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
                "reminders_sent": "TEXT DEFAULT '[]'",
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

    async def _create_tables(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                registration_date TEXT NOT NULL DEFAULT (datetime('now')),
                source TEXT DEFAULT 'direct',
                source_chat_id INTEGER,
                referrer_id INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_activity TEXT,
                total_lessons INTEGER DEFAULT 0,
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS admin_sessions (
                admin_id INTEGER PRIMARY KEY,
                is_authenticated INTEGER NOT NULL DEFAULT 0,
                auth_time TEXT,
                session_expires TEXT,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TEXT
            );
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price_per_hour REAL NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS time_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                is_available INTEGER NOT NULL DEFAULT 1,
                is_recurring INTEGER NOT NULL DEFAULT 0,
                recurring_day INTEGER,
                slot_type TEXT DEFAULT 'regular',
                version INTEGER DEFAULT 0,
                UNIQUE(date, start_time)
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                slot_id INTEGER NOT NULL,
                subject_id INTEGER,
                booking_type TEXT NOT NULL DEFAULT 'trial',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                confirmed_at TEXT,
                cancelled_at TEXT,
                cancel_reason TEXT,
                reminder_sent INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY (student_id) REFERENCES students(user_id),
                FOREIGN KEY (slot_id) REFERENCES time_slots(id)
            );
            CREATE TABLE IF NOT EXISTS homework (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_id INTEGER,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                file_ids TEXT DEFAULT '[]',
                assigned_date TEXT NOT NULL DEFAULT (datetime('now')),
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'assigned',
                grade TEXT,
                feedback TEXT,
                submitted_at TEXT,
                submitted_file_ids TEXT DEFAULT '[]',
                FOREIGN KEY (student_id) REFERENCES students(user_id)
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                payment_method TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                paid_at TEXT,
                reminder_count INTEGER DEFAULT 0,
                last_reminder TEXT,
                FOREIGN KEY (student_id) REFERENCES students(user_id)
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                booking_id INTEGER,
                rating INTEGER NOT NULL,
                text TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_published INTEGER DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students(user_id)
            );
            CREATE TABLE IF NOT EXISTS faq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                keywords TEXT DEFAULT '[]',
                order_num INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS mailings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT 'all',
                target_chat_ids TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                sent_at TEXT,
                total_sent INTEGER DEFAULT 0,
                total_errors INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS ad_chats (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT DEFAULT '',
                added_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1,
                total_leads INTEGER DEFAULT 0,
                last_mailing TEXT
            );
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                referral_code TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                bonus_applied INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS funnel_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                source TEXT,
                source_chat_id INTEGER,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                variant_a_text TEXT NOT NULL,
                variant_b_text TEXT NOT NULL,
                variant_a_sends INTEGER DEFAULT 0,
                variant_a_clicks INTEGER DEFAULT 0,
                variant_b_sends INTEGER DEFAULT 0,
                variant_b_clicks INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
             CREATE TABLE IF NOT EXISTS dnd_schedule (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 day_of_week INTEGER,
                 start_time TEXT NOT NULL,
                 end_time TEXT NOT NULL,
                 auto_reply_text TEXT DEFAULT
                     'Сейчас идёт занятие. Я отвечу вам позже!'
             );
             -- ИСПРАВЛЕНИЕ: защита от двойного бронирования одного слота
             -- (только активные записи; отменённые слоты освобождаются)
            CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_slot_active
                 ON bookings(slot_id)
                 WHERE status IN ('pending', 'confirmed');
            -- Шаблоны быстрых ответов репетитора
            CREATE TABLE IF NOT EXISTS reply_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            -- Отложенные сообщения ученикам
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                send_at TEXT NOT NULL,
                sent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            -- Материалы (файлы) по предметам
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        await self.db.commit()
    # =================== СТУДЕНТЫ ===================
    async def add_student(self, user_id: int, full_name: str,
                          username: str = None, phone: str = None,
                          source: str = "direct",
                          source_chat_id: int = None,
                          referrer_id: int = None) -> bool:
        try:
            await self.db.execute(
                """INSERT OR IGNORE INTO students
                   (user_id, username, full_name, phone, source,
                    source_chat_id, referrer_id, last_activity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (user_id, username, full_name, phone,
                 source, source_chat_id, referrer_id)
            )
            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"[add_student] Failed: {e}")
            return False
    async def get_student(self, user_id: int) -> Optional[dict]:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM students WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[get_student] Failed: {e}")
            return None
    async def get_all_students(self, active_only: bool = True) -> list:
        try:
            query = "SELECT * FROM students"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY registration_date DESC"
            cursor = await self.db.execute(query)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_all_students] Failed: {e}")
            return []
    async def get_inactive_students(self, days: int = 30) -> list:
        try:
            cursor = await self.db.execute(
                """SELECT * FROM students
                   WHERE is_active = 1
                   AND (last_activity IS NULL OR
                        last_activity < datetime('now', ?))""",
                (f"-{days} days",)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_inactive_students] Failed: {e}")
            return []
    async def update_student_activity(self, user_id: int):
        try:
            await self.db.execute(
                """UPDATE students SET last_activity = datetime('now')
                   WHERE user_id = ?""",
                (user_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[update_student_activity] Failed: {e}")
    async def update_student(self, user_id: int, **kwargs):
        try:
            if not kwargs:
                return
            set_clause = ", ".join(
                f"{k} = ?" for k in kwargs.keys()
            )
            values = list(kwargs.values()) + [user_id]
            await self.db.execute(
                f"UPDATE students SET {set_clause} WHERE user_id = ?",
                values
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[update_student] Failed: {e}")
    # =================== АДМИН СЕССИИ ===================
    async def check_admin_session(self, admin_id: int) -> bool:
        try:
            cursor = await self.db.execute(
                """SELECT is_authenticated, session_expires
                   FROM admin_sessions WHERE admin_id = ?""",
                (admin_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return False
            if not row["is_authenticated"]:
                return False
            if row["session_expires"]:
                expires = datetime.fromisoformat(row["session_expires"])
                if datetime.now() > expires:
                    await self.logout_admin(admin_id)
                    return False
            return True
        except Exception as e:
            logger.error(f"[check_admin_session] Failed: {e}")
            return False
    async def authenticate_admin(self, admin_id: int, hours: int = 12):
        try:
            expires = (
                datetime.now() + timedelta(hours=hours)
            ).isoformat()
            await self.db.execute(
                """INSERT OR REPLACE INTO admin_sessions
                   (admin_id, is_authenticated, auth_time, session_expires, failed_attempts)
                   VALUES (?, 1, datetime('now'), ?, 0)""",
                (admin_id, expires)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[authenticate_admin] Failed: {e}")
    async def logout_admin(self, admin_id: int):
        try:
            await self.db.execute(
                """UPDATE admin_sessions SET is_authenticated = 0
                   WHERE admin_id = ?""",
                (admin_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[logout_admin] Failed: {e}")
    # =================== ПРЕДМЕТЫ ===================
    async def add_subject(self, name: str, price: float,
                          description: str = "") -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO subjects
                   (name, price_per_hour, description)
                   VALUES (?, ?, ?)""",
                (name, price, description)
            )
            await self.db.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"[add_subject] Failed: {e}")
            return 0
    async def get_subjects(self, active_only: bool = True) -> list:
        try:
            query = "SELECT * FROM subjects"
            if active_only:
                query += " WHERE is_active = 1"
            cursor = await self.db.execute(query)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_subjects] Failed: {e}")
            return []
    async def get_subject(self, subject_id: int) -> Optional[dict]:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM subjects WHERE id = ?", (subject_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[get_subject] Failed: {e}")
            return None
    async def delete_subject(self, subject_id: int):
        try:
            await self.db.execute(
                "UPDATE subjects SET is_active = 0 WHERE id = ?",
                (subject_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[delete_subject] Failed: {e}")
    # =================== СЛОТЫ ===================
    async def add_time_slot(self, date_str: str, start_time: str,
                            end_time: str, is_recurring: bool = False,
                            recurring_day: int = None,
                            slot_type: str = "regular") -> int:
        try:
            cursor = await self.db.execute(
                """INSERT OR IGNORE INTO time_slots
                   (date, start_time, end_time, is_recurring,
                    recurring_day, slot_type)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (date_str, start_time, end_time,
                 int(is_recurring), recurring_day, slot_type)
            )
            await self.db.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            logger.error(f"[add_time_slot] Failed: {e}")
            return 0
    async def get_available_slots(self, from_date: str = None,
                                  days_ahead: int = 14) -> list:
        try:
            if not from_date:
                from_date = date.today().isoformat()
            to_date = (
                date.fromisoformat(from_date) +
                timedelta(days=days_ahead)
            ).isoformat()
            cursor = await self.db.execute(
                """SELECT * FROM time_slots
                   WHERE is_available = 1
                   AND date >= ? AND date <= ?
                   ORDER BY date, start_time""",
                (from_date, to_date)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_available_slots] Failed: {e}")
            return []
    async def get_slot(self, slot_id: int) -> Optional[dict]:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM time_slots WHERE id = ?", (slot_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[get_slot] Failed: {e}")
            return None
    async def block_slot(self, slot_id: int):
        try:
            await self.db.execute(
                "UPDATE time_slots SET is_available = 0 WHERE id = ?",
                (slot_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[block_slot] Failed: {e}")
    async def unblock_slot(self, slot_id: int):
        try:
            await self.db.execute(
                "UPDATE time_slots SET is_available = 1 WHERE id = ?",
                (slot_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[unblock_slot] Failed: {e}")
    async def get_all_slots_for_date(self, date_str: str) -> list:
        try:
            cursor = await self.db.execute(
                """SELECT * FROM time_slots WHERE date = ?
                   ORDER BY start_time""",
                (date_str,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_all_slots_for_date] Failed: {e}")
            return []
    async def get_slots_for_date(self, date_str: str) -> list:
        """Алиас для get_all_slots_for_date."""
        return await self.get_all_slots_for_date(date_str)
    # =================== БРОНИРОВАНИЯ ===================
    async def create_booking(self, student_id: int, slot_id: int,
                             subject_id: int = None,
                             booking_type: str = "trial") -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO bookings
                   (student_id, slot_id, subject_id, booking_type)
                   VALUES (?, ?, ?, ?)""",
                (student_id, slot_id, subject_id, booking_type)
            )
            await self.block_slot(slot_id)
            await self.db.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"[create_booking] Failed: {e}")
            return 0
    async def get_booking(self, booking_id: int) -> Optional[dict]:
        try:
            cursor = await self.db.execute(
                """SELECT b.*, ts.date, ts.start_time, ts.end_time,
                          s.name as subject_name
                   FROM bookings b
                   LEFT JOIN time_slots ts ON b.slot_id = ts.id
                   LEFT JOIN subjects s ON b.subject_id = s.id
                   WHERE b.id = ?""",
                (booking_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[get_booking] Failed: {e}")
            return None
    async def get_student_bookings(self, student_id: int,
                                   status: str = None) -> list:
        try:
            query = """SELECT b.*, ts.date, ts.start_time, ts.end_time,
                              s.name as subject_name
                       FROM bookings b
                       LEFT JOIN time_slots ts ON b.slot_id = ts.id
                       LEFT JOIN subjects s ON b.subject_id = s.id
                       WHERE b.student_id = ?"""
            params = [student_id]
            if status:
                query += " AND b.status = ?"
                params.append(status)
            query += " ORDER BY ts.date DESC"
            cursor = await self.db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_student_bookings] Failed: {e}")
            return []
    async def get_today_bookings(self) -> list:
        try:
            # ИСПРАВЛЕНО: учитываем таймзону из .env
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo(config.TIMEZONE)).date().isoformat()
            cursor = await self.db.execute(
                """SELECT b.*, ts.date, ts.start_time, ts.end_time,
                          s.name as subject_name,
                          st.full_name, st.username
                   FROM bookings b
                   LEFT JOIN time_slots ts ON b.slot_id = ts.id
                   LEFT JOIN subjects s ON b.subject_id = s.id
                   LEFT JOIN students st ON b.student_id = st.user_id
                   WHERE ts.date = ?
                   AND b.status IN ('pending', 'confirmed')
                   ORDER BY ts.start_time""",
                (today,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_today_bookings] Failed: {e}")
            return []
    async def get_upcoming_bookings(self,
                                    minutes_ahead: int = 60) -> list:
        """Занятия в окне [now, now + minutes_ahead] для напоминаний.

        ИСПРАВЛЕНО (напоминания не приходили):
        1. Теперь время берётся в таймзоне из .env (TIMEZONE), а не
           серверное (на хостинге — UTC, из-за чего окно сдвигалось на часы).
        2. Учитываются записи со статусом 'pending' и 'confirmed'.
           Новые записи создаются как 'pending', и если репетитор их не
           подтверждает — напоминания по старому коду не шли никогда.
        3. Отслеживаются уже отправленные напоминания по минутам
           (колонка reminders_sent, JSON-список), поэтому каждый пункт
           REMINDER_BEFORE_MINUTES (60 и 15) отправляется ровно один раз.
        4. ИСПРАВЛЕНО (v2): окно теперь [+X-10 мин, +X мин], а не
           [сейчас, +X мин]. Раньше запись за 1 минуту до занятия
           попадала сразу во ВСЕ окна, и бот в течение 5 минут
           присылал подряд «через 60 минут» и «через 15 минут»,
           хотя до занятия оставалась 1 минута.
        """
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(config.TIMEZONE)
            now = datetime.now(tz)
            today = now.date().isoformat()
            tomorrow = (now.date() + timedelta(days=1)).isoformat()
            # Окно шириной 10 минут, нацеленное на момент "+minutes_ahead":
            # напоминание «за 60 минут» — для занятий, начинающихся
            # через 50–60 минут; «за 15» — через 5–15 минут.
            # Запись за 1 минуту до начала не попадает ни в одно окно.
            window_min = now + timedelta(minutes=minutes_ahead - 10)
            window_max = now + timedelta(minutes=minutes_ahead)
            # ИСПРАВЛЕНО: раньше окно, пересекающее полночь, просто
            # игнорировалось (return []) — напоминания для занятий сразу
            # после 00:00 никогда не приходили. Теперь берём слоты за
            # сегодня и завтра и сравниваем полные дата+время.
            cursor = await self.db.execute(
                """SELECT b.*, ts.date, ts.start_time, ts.end_time,
                          s.name as subject_name,
                          st.full_name,
                          st.user_id as student_user_id
                   FROM bookings b
                   LEFT JOIN time_slots ts ON b.slot_id = ts.id
                   LEFT JOIN subjects s ON b.subject_id = s.id
                   LEFT JOIN students st ON b.student_id = st.user_id
                   WHERE ts.date IN (?, ?)
                   AND b.status IN ('pending', 'confirmed')""",
                (today, tomorrow)
            )
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    slot_dt = datetime.fromisoformat(
                        f"{d['date']}T{d['start_time'][:5]}:00"
                    ).replace(tzinfo=tz)
                except (ValueError, TypeError):
                    continue
                if not (window_min <= slot_dt <= window_max):
                    continue
                try:
                    sent = json.loads(d.get("reminders_sent") or "[]")
                except (ValueError, TypeError):
                    # Старые данные: считаем флаг reminder_sent за отправку 60-мин
                    sent = [minutes_ahead] if d.get("reminder_sent") else []
                if minutes_ahead in sent:
                    continue
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"[get_upcoming_bookings] Failed: {e}")
            return []
    async def mark_reminder_sent(self, booking_id: int, minutes: int = 60):
        """ИСПРАВЛЕНО: запоминает, какие напоминания (60/15 мин) уже
        отправлены по конкретной записи, чтобы каждое отправлялось один раз,
        а не блокировало остальные одним общим флагом."""
        try:
            cursor = await self.db.execute(
                "SELECT reminders_sent, reminder_sent FROM bookings WHERE id = ?",
                (booking_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return
            try:
                sent = json.loads(row[0] or "[]")
            except (ValueError, TypeError):
                sent = []
            if minutes not in sent:
                sent.append(minutes)
            await self.db.execute(
                """UPDATE bookings
                   SET reminders_sent = ?, reminder_sent = 1
                   WHERE id = ?""",
                (json.dumps(sent), booking_id)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[mark_reminder_sent] Failed: {e}")
    async def cancel_booking(self, booking_id: int, reason: str = ""):
        try:
            booking = await self.get_booking(booking_id)
            if booking:
                await self.db.execute(
                    """UPDATE bookings SET status = 'cancelled',
                       cancelled_at = datetime('now'),
                       cancel_reason = ?
                       WHERE id = ?""",
                    (reason, booking_id)
                )
                await self.unblock_slot(booking["slot_id"])
                await self.db.commit()
        except Exception as e:
            logger.error(f"[cancel_booking] Failed: {e}")
    async def complete_booking(self, booking_id: int):
        try:
            await self.db.execute(
                """UPDATE bookings SET status = 'completed'
                   WHERE id = ?""",
                (booking_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[complete_booking] Failed: {e}")
    # =================== ДОМАШНИЕ ЗАДАНИЯ ===================
    async def add_homework(self, student_id: int, title: str,
                           description: str = "",
                           subject_id: int = None,
                           due_date: str = None,
                           file_ids: list = None) -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO homework
                   (student_id, subject_id, title, description,
                    file_ids, due_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, subject_id, title, description,
                 json.dumps(file_ids or []), due_date)
            )
            await self.db.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"[add_homework] Failed: {e}")
            return 0
    async def get_student_homework(self, student_id: int,
                                   status: str = None) -> list:
        try:
            query = """SELECT h.*, s.name as subject_name
                       FROM homework h
                       LEFT JOIN subjects s ON h.subject_id = s.id
                       WHERE h.student_id = ?"""
            params = [student_id]
            if status:
                query += " AND h.status = ?"
                params.append(status)
            query += " ORDER BY h.assigned_date DESC"
            cursor = await self.db.execute(query, params)
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["file_ids"] = json.loads(
                        d.get("file_ids", "[]")
                    )
                except Exception:
                    d["file_ids"] = []
                try:
                    d["submitted_file_ids"] = json.loads(
                        d.get("submitted_file_ids", "[]")
                    )
                except Exception:
                    d["submitted_file_ids"] = []
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"[get_student_homework] Failed: {e}")
            return []
    async def get_homework_due(self, due_date: str) -> list:
        """Невыполненные ДЗ с дедлайном на указанную дату (status='assigned')."""
        try:
            cursor = await self.db.execute(
                """SELECT h.*, st.full_name, st.username
                   FROM homework h
                   LEFT JOIN students st ON h.student_id = st.user_id
                   WHERE h.due_date = ? AND h.status = 'assigned'
                   ORDER BY st.full_name""",
                (due_date,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_homework_due] Failed: {e}")
            return []
    async def get_homework_by_id(self, hw_id: int) -> Optional[dict]:
        """НОВЫЙ МЕТОД: получить ДЗ по ID."""
        try:
            cursor = await self.db.execute(
                "SELECT * FROM homework WHERE id = ?", (hw_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[get_homework_by_id] Failed: {e}")
            return None
    async def get_all_homework(self) -> list:
        """НОВЫЙ МЕТОД: все ДЗ (для админа)."""
        try:
            cursor = await self.db.execute(
                """SELECT h.*, s.name as subject_name, st.full_name as student_name
                   FROM homework h
                   LEFT JOIN subjects s ON h.subject_id = s.id
                   LEFT JOIN students st ON h.student_id = st.user_id
                   ORDER BY h.assigned_date DESC"""
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_all_homework] Failed: {e}")
            return []
    async def get_pending_homework(self) -> list:
        """НОВЫЙ МЕТОД: ДЗ на проверке (status=submitted)."""
        try:
            cursor = await self.db.execute(
                """SELECT h.*, s.name as subject_name, st.full_name as student_name
                   FROM homework h
                   LEFT JOIN subjects s ON h.subject_id = s.id
                   LEFT JOIN students st ON h.student_id = st.user_id
                   WHERE h.status = 'submitted'
                   ORDER BY h.submitted_at"""
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_pending_homework] Failed: {e}")
            return []
    async def submit_homework(self, hw_id: int,
                              file_ids: list = None):
        try:
            await self.db.execute(
                """UPDATE homework SET status = 'submitted',
                   submitted_at = datetime('now'),
                   submitted_file_ids = ?
                   WHERE id = ?""",
                (json.dumps(file_ids or []), hw_id)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[submit_homework] Failed: {e}")
    async def grade_homework(self, hw_id: int, grade: str,
                             feedback: str = ""):
        try:
            await self.db.execute(
                """UPDATE homework SET status = 'graded',
                   grade = ?, feedback = ?
                   WHERE id = ?""",
                (grade, feedback, hw_id)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[grade_homework] Failed: {e}")
    # =================== ОПЛАТЫ ===================
    async def create_payment(self, student_id: int, amount: float,
                             description: str = "") -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO payments
                   (student_id, amount, description)
                   VALUES (?, ?, ?)""",
                (student_id, amount, description)
            )
            await self.db.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"[create_payment] Failed: {e}")
            return 0
    async def get_pending_payments(self,
                                   student_id: int = None) -> list:
        try:
            query = """SELECT p.*, st.full_name, st.username
                       FROM payments p
                       LEFT JOIN students st
                           ON p.student_id = st.user_id
                       WHERE p.status = 'pending'"""
            params = []
            if student_id:
                query += " AND p.student_id = ?"
                params.append(student_id)
            query += " ORDER BY p.created_at DESC"
            cursor = await self.db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_pending_payments] Failed: {e}")
            return []
    async def get_payment_by_id(self, pay_id: int) -> Optional[dict]:
        """Платёж по ID (с данными ученика — для уведомлений репетитора)."""
        try:
            cursor = await self.db.execute(
                """SELECT p.*, st.full_name, st.username
                   FROM payments p
                   LEFT JOIN students st ON p.student_id = st.user_id
                   WHERE p.id = ?""",
                (pay_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[get_payment_by_id] Failed: {e}")
            return None
    async def report_payment_paid(self, payment_id: int) -> bool:
        """ИСПРАВЛЕНИЕ: ученик нажал «Я оплатил» — переводим счёт в
        статус 'reported' (ожидает подтверждения репетитором).
        Без этого счёт оставался 'pending' вечно и бот каждый день
        повторно присылал ученику напоминание об оплате."""
        try:
            cursor = await self.db.execute(
                """UPDATE payments SET status = 'reported'
                   WHERE id = ? AND status = 'pending'""",
                (payment_id,)
            )
            await self.db.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[report_payment_paid] Failed: {e}")
            return False
    async def get_reported_payments(self, student_id: int = None) -> list:
        """Счета, которые ученик пометил оплаченными, но репетитор ещё
        не подтвердил поступление."""
        try:
            query = """SELECT p.*, st.full_name, st.username
                       FROM payments p
                       LEFT JOIN students st ON p.student_id = st.user_id
                       WHERE p.status = 'reported'"""
            params = []
            if student_id:
                query += " AND p.student_id = ?"
                params.append(student_id)
            query += " ORDER BY p.created_at DESC"
            cursor = await self.db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_reported_payments] Failed: {e}")
            return []
    async def get_all_payments(self) -> list:
        """НОВЫЙ МЕТОД: все оплаченные платежи."""
        try:
            cursor = await self.db.execute(
                """SELECT p.*, st.full_name, st.username
                   FROM payments p
                   LEFT JOIN students st ON p.student_id = st.user_id
                   WHERE p.status = 'paid'
                   ORDER BY p.paid_at DESC"""
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_all_payments] Failed: {e}")
            return []
    async def confirm_payment(self, payment_id: int,
                              method: str = "manual"):
        try:
            await self.db.execute(
                """UPDATE payments SET status = 'paid',
                   paid_at = datetime('now'),
                   payment_method = ?
                   WHERE id = ?""",
                (method, payment_id)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[confirm_payment] Failed: {e}")
    async def get_payment_stats(self, period_days: int = 30) -> dict:
        try:
            cursor = await self.db.execute(
                """SELECT
                    COUNT(*) as total_payments,
                    SUM(CASE WHEN status='paid' THEN amount ELSE 0 END) as total_paid,
                    SUM(CASE WHEN status='pending' THEN amount ELSE 0 END) as total_pending,
                    SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) as paid_count,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending_count
                   FROM payments
                   WHERE created_at >= datetime('now', ?)""",
                (f"-{period_days} days",)
            )
            row = await cursor.fetchone()
            return dict(row) if row else {}
        except Exception as e:
            logger.error(f"[get_payment_stats] Failed: {e}")
            return {}
    # =================== ОТЗЫВЫ ===================
    async def create_review(self, student_id: int, rating: int,
                            text: str = "",
                            booking_id: int = None) -> int:
        """НОВЫЙ МЕТОД: создать отзыв."""
        try:
            cursor = await self.db.execute(
                """INSERT INTO reviews (student_id, booking_id, rating, text)
                   VALUES (?, ?, ?, ?)""",
                (student_id, booking_id, rating, text)
            )
            await self.db.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"[create_review] Failed: {e}")
            return 0
    async def get_reviews(self, published_only: bool = False) -> list:
        try:
            query = """SELECT r.*, st.full_name FROM reviews r
                       LEFT JOIN students st
                           ON r.student_id = st.user_id"""
            if published_only:
                query += " WHERE r.is_published = 1"
            query += " ORDER BY r.created_at DESC"
            cursor = await self.db.execute(query)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_reviews] Failed: {e}")
            return []
    async def get_all_reviews(self) -> list:
        """НОВЫЙ МЕТОД: все отзывы."""
        return await self.get_reviews(published_only=False)
    async def publish_review(self, review_id: int):
        try:
            await self.db.execute(
                "UPDATE reviews SET is_published = 1 WHERE id = ?",
                (review_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[publish_review] Failed: {e}")
    async def get_average_rating(self) -> float:
        try:
            cursor = await self.db.execute(
                "SELECT AVG(rating) as avg_rating FROM reviews"
            )
            row = await cursor.fetchone()
            val = row["avg_rating"] if row else None
            return round(float(val), 2) if val else 0.0
        except Exception as e:
            logger.error(f"[get_average_rating] Failed: {e}")
            return 0.0
    # =================== FAQ ===================
    async def add_faq(self, question: str, answer: str,
                      keywords: list = None) -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO faq (question, answer, keywords)
                   VALUES (?, ?, ?)""",
                (question, answer, json.dumps(keywords or []))
            )
            await self.db.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"[add_faq] Failed: {e}")
            return 0
    async def get_all_faq(self) -> list:
        try:
            cursor = await self.db.execute(
                """SELECT * FROM faq WHERE is_active = 1
                   ORDER BY order_num"""
            )
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["keywords"] = json.loads(
                        d.get("keywords", "[]")
                    )
                except Exception:
                    d["keywords"] = []
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"[get_all_faq] Failed: {e}")
            return []
    async def find_faq_answer(self,
                              text: str) -> Optional[dict]:
        try:
            faqs = await self.get_all_faq()
            text_lower = text.lower()
            for faq in faqs:
                keywords = faq.get("keywords", [])
                for kw in keywords:
                    if kw.lower() in text_lower:
                        return faq
            return None
        except Exception as e:
            logger.error(f"[find_faq_answer] Failed: {e}")
            return None
    async def delete_faq(self, faq_id: int):
        try:
            await self.db.execute(
                "UPDATE faq SET is_active = 0 WHERE id = ?",
                (faq_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[delete_faq] Failed: {e}")
    # =================== ЧАТЫ И РАССЫЛКИ ===================
    async def add_ad_chat(self, chat_id: int,
                          chat_title: str = ""):
        try:
            await self.db.execute(
                """INSERT OR IGNORE INTO ad_chats
                   (chat_id, chat_title)
                   VALUES (?, ?)""",
                (chat_id, chat_title)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[add_ad_chat] Failed: {e}")
    async def get_ad_chats(self,
                           active_only: bool = True) -> list:
        try:
            query = "SELECT * FROM ad_chats"
            if active_only:
                query += " WHERE is_active = 1"
            cursor = await self.db.execute(query)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_ad_chats] Failed: {e}")
            return []
    async def increment_chat_leads(self, chat_id: int):
        try:
            await self.db.execute(
                """UPDATE ad_chats
                   SET total_leads = total_leads + 1
                   WHERE chat_id = ?""",
                (chat_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[increment_chat_leads] Failed: {e}")
    async def create_mailing(self, text: str,
                             target_type: str = "all") -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO mailings (text, target_type)
                   VALUES (?, ?)""",
                (text, target_type)
            )
            await self.db.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"[create_mailing] Failed: {e}")
            return 0
    async def update_mailing_status(self, mailing_id: int,
                                    status: str = "sent",
                                    total_sent: int = 0,
                                    total_errors: int = 0):
        """НОВЫЙ МЕТОД (расширенный): обновить статус рассылки."""
        try:
            await self.db.execute(
                """UPDATE mailings SET status = ?,
                   sent_at = datetime('now'),
                   total_sent = ?, total_errors = ?
                   WHERE id = ?""",
                (status, total_sent, total_errors, mailing_id)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[update_mailing_status] Failed: {e}")
    async def update_mailing_stats(self, mailing_id: int,
                                   sent: int, errors: int):
        """Обратная совместимость."""
        await self.update_mailing_status(mailing_id, "sent", sent, errors)
    async def get_mailings(self, limit: int = 20) -> list:
        try:
            cursor = await self.db.execute(
                """SELECT * FROM mailings
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_mailings] Failed: {e}")
            return []
    # =================== РЕФЕРАЛЫ ===================
    async def create_referral(self, referrer_id: int,
                              referred_id: int,
                              referral_code: str) -> bool:
        try:
            # Защита: проверяем, не был ли этот юзер уже приглашен
            cursor = await self.db.execute(
                "SELECT id FROM referrals WHERE referred_id = ?",
                (referred_id,)
            )
            if await cursor.fetchone():
                return False  # Такой реферал уже существует
            await self.db.execute(
                """INSERT INTO referrals
                   (referrer_id, referred_id, referral_code)
                   VALUES (?, ?, ?)""",
                (referrer_id, referred_id, referral_code)
            )
            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"[create_referral] Failed: {e}")
            return False
    async def get_referral_stats(self,
                                 referrer_id: int) -> dict:
        try:
            cursor = await self.db.execute(
                """SELECT COUNT(*) as total_referrals,
                          COUNT(CASE WHEN status='completed'
                              THEN 1 END) as completed
                   FROM referrals WHERE referrer_id = ?""",
                (referrer_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else {
                "total_referrals": 0, "completed": 0
            }
        except Exception as e:
            logger.error(f"[get_referral_stats] Failed: {e}")
            return {"total_referrals": 0, "completed": 0}
    async def get_all_referrals(self) -> list:
        """НОВЫЙ МЕТОД: все рефералы (для админа)."""
        try:
            cursor = await self.db.execute(
                """SELECT r.*,
                          st1.full_name as referrer_name,
                          st2.full_name as referred_name
                   FROM referrals r
                   LEFT JOIN students st1 ON r.referrer_id = st1.user_id
                   LEFT JOIN students st2 ON r.referred_id = st2.user_id
                   ORDER BY r.created_at DESC"""
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_all_referrals] Failed: {e}")
            return []
    # =================== ВОРОНКА (ИСПРАВЛЕНА опечатка funnel→funnel) ===================
    async def log_funnel_event(self, user_id: int,
                               event_type: str,
                               source: str = None,
                               source_chat_id: int = None,
                               metadata: dict = None):
        """Логирование события воронки."""
        try:
            await self.db.execute(
                """INSERT INTO funnel_events
                   (user_id, event_type, source,
                    source_chat_id, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, event_type, source, source_chat_id,
                 json.dumps(metadata or {}))
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[log_funnel_event] Failed: {e}")
    async def get_funnel_stats(self, period_days: int = 30) -> dict:
        """Статистика воронки за период."""
        try:
            events = [
                "ad_seen", "bot_started", "trial_booked",
                "trial_attended", "became_regular"
            ]
            stats = {}
            for event in events:
                cursor = await self.db.execute(
                    """SELECT COUNT(DISTINCT user_id) as count
                       FROM funnel_events
                       WHERE event_type = ?
                       AND created_at >= datetime('now', ?)""",
                    (event, f"-{period_days} days")
                )
                row = await cursor.fetchone()
                stats[event] = row["count"] if row else 0
            return stats
        except Exception as e:
            logger.error(f"[get_funnel_stats] Failed: {e}")
            return {}
    async def get_chat_performance(self) -> list:
        try:
            cursor = await self.db.execute(
                """SELECT ac.chat_id, ac.chat_title,
                          ac.total_leads,
                          COUNT(DISTINCT fe.user_id) as unique_users
                   FROM ad_chats ac
                   LEFT JOIN funnel_events fe
                       ON ac.chat_id = fe.source_chat_id
                   WHERE ac.is_active = 1
                   GROUP BY ac.chat_id
                   ORDER BY ac.total_leads DESC"""
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_chat_performance] Failed: {e}")
            return []
    # =================== НАСТРОЙКИ ===================
    async def get_setting(self, key: str,
                          default: str = "") -> str:
        try:
            cursor = await self.db.execute(
                "SELECT value FROM bot_settings WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            return row["value"] if row else default
        except Exception as e:
            logger.error(f"[get_setting] Failed: {e}")
            return default
    async def set_setting(self, key: str, value: str):
        try:
            await self.db.execute(
                """INSERT OR REPLACE INTO bot_settings
                   (key, value, updated_at)
                   VALUES (?, ?, datetime('now'))""",
                (key, value)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[set_setting] Failed: {e}")
    # =================== DND ===================
    async def is_dnd_active(self) -> tuple[bool, str]:
        """Проверка, активен ли DND. Возвращает (is_active, auto_reply)."""
        try:
            enabled = await self.get_setting("dnd_enabled", "0")
            if enabled != "1":
                return False, ""
            start = await self.get_setting("dnd_start", "09:00")
            end = await self.get_setting("dnd_end", "21:00")
            auto_reply = await self.get_setting(
                "dnd_auto_reply",
                "Сейчас идёт занятие. Я отвечу вам позже!"
            )
            # ИСПРАВЛЕНО: время берём в таймзоне из .env, а не серверное.
            # На хостинге (UTC) окно DND 09:00–21:00 МСК сдвигалось на 3 часа
            # и выглядело так, будто DND «не работает».
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(config.TIMEZONE))
            current_minutes = now.hour * 60 + now.minute
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            start_minutes = sh * 60 + sm
            end_minutes = eh * 60 + em
            if start_minutes <= end_minutes:
                is_active = start_minutes <= current_minutes < end_minutes
            else:
                is_active = current_minutes >= start_minutes or current_minutes < end_minutes
            return is_active, auto_reply
        except Exception as e:
            logger.error(f"[is_dnd_active] Failed: {e}")
            return False, ""
    async def set_dnd(self, enabled: bool):
        """НОВЫЙ МЕТОД: включить/выключить DND."""
        try:
            await self.set_setting("dnd_enabled", "1" if enabled else "0")
        except Exception as e:
            logger.error(f"[set_dnd] Failed: {e}")
    # =================== ЛОГИРОВАНИЕ ===================
    async def log_action(self, user_id: int, action: str,
                         details: dict = None):
        """Логирование действий (ИСПРАВЛЕНО: ошибки логируются)."""
        try:
            await self.db.execute(
                """INSERT INTO action_logs
                   (user_id, action, details)
                   VALUES (?, ?, ?)""",
                (user_id, action, json.dumps(details or {}))
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[log_action] Failed to log {action}: {e}")
    # =================== ДАШБОРД ===================
    async def get_dashboard_stats(self) -> dict:
        try:
            stats = {
                "total_students": 0,
                "new_students_month": 0,
                "today_bookings": 0,
                "trial_bookings_month": 0,
                "trial_conversion": 0.0,
                "avg_rating": 0.0,
                "revenue_month": 0.0,
                "pending_payments": 0.0,
            }
            # Всего учеников
            cursor = await self.db.execute(
                "SELECT COUNT(*) as cnt FROM students WHERE is_active = 1"
            )
            row = await cursor.fetchone()
            if row:
                stats["total_students"] = row["cnt"]
            # Новых за месяц
            cursor = await self.db.execute(
                """SELECT COUNT(*) as cnt FROM students
                   WHERE registration_date >= datetime('now', '-30 days')"""
            )
            row = await cursor.fetchone()
            if row:
                stats["new_students_month"] = row["cnt"]
            # Записей сегодня
            today = date.today().isoformat()
            cursor = await self.db.execute(
                """SELECT COUNT(*) as cnt FROM bookings b
                   LEFT JOIN time_slots ts ON b.slot_id = ts.id
                   WHERE ts.date = ?""",
                (today,)
            )
            row = await cursor.fetchone()
            if row:
                stats["today_bookings"] = row["cnt"]
            # Пробных за месяц
            cursor = await self.db.execute(
                """SELECT COUNT(*) as cnt FROM bookings
                   WHERE booking_type = 'trial'
                   AND created_at >= datetime('now', '-30 days')"""
            )
            row = await cursor.fetchone()
            if row:
                stats["trial_bookings_month"] = row["cnt"]
            # Конверсия
            if stats["trial_bookings_month"] > 0:
                cursor = await self.db.execute(
                    """SELECT COUNT(*) as cnt FROM bookings
                       WHERE status = 'completed'
                       AND created_at >= datetime('now', '-30 days')"""
                )
                row = await cursor.fetchone()
                completed = row["cnt"] if row else 0
                stats["trial_conversion"] = round(
                    completed / stats["trial_bookings_month"] * 100, 1
                )
            # Рейтинг
            stats["avg_rating"] = await self.get_average_rating()
            # Доход
            cursor = await self.db.execute(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM payments
                   WHERE status = 'paid'
                   AND paid_at >= datetime('now', '-30 days')"""
            )
            row = await cursor.fetchone()
            if row:
                stats["revenue_month"] = round(row["total"], 2)
            # Ожидают оплаты
            cursor = await self.db.execute(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM payments WHERE status = 'pending'"""
            )
            row = await cursor.fetchone()
            if row:
                stats["pending_payments"] = round(row["total"], 2)
            return stats
        except Exception as e:
            logger.error(f"[get_dashboard_stats] Failed: {e}")
            return {
                "total_students": 0,
                "new_students_month": 0,
                "today_bookings": 0,
                "trial_bookings_month": 0,
                "trial_conversion": 0.0,
                "avg_rating": 0.0,
                "revenue_month": 0.0,
                "pending_payments": 0.0,
            }
    # =================== A/B ТЕСТЫ ===================
    async def get_active_ab_tests(self) -> list:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM ab_tests WHERE status = 'active'"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[get_active_ab_tests] Failed: {e}")
            return []
    async def increment_ab_stat(self, test_id: int,
                                variant: str,
                                stat_type: str):
        """Увеличить счётчик A/B теста. variant: 'A'/'B', stat_type: 'sends'/'clicks'."""
        try:
            column = f"variant_{variant.lower()}_{stat_type}"
            # Белый список колонок для безопасности
            allowed = {
                "variant_a_sends", "variant_a_clicks",
                "variant_b_sends", "variant_b_clicks"
            }
            if column not in allowed:
                logger.error(f"[increment_ab_stat] Invalid column: {column}")
                return
            await self.db.execute(
                f"UPDATE ab_tests SET {column} = {column} + 1 WHERE id = ?",
                (test_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[increment_ab_stat] Failed: {e}")

    # =================== АБОНЕМЕНТЫ (пакеты занятий) ===================
    async def add_lessons(self, user_id: int, count: int) -> int:
        """Пополнить баланс занятий по абонементу. Возвращает новый баланс."""
        try:
            cursor = await self.db.execute(
                "UPDATE students SET lessons_balance = lessons_balance + ?"
                " WHERE user_id = ?",
                (count, user_id)
            )
            await self.db.commit()
            student = await self.get_student(user_id)
            return int((student or {}).get("lessons_balance") or 0)
        except Exception as e:
            logger.error(f"[add_lessons] Failed: {e}")
            return 0

    async def consume_lesson(self, user_id: int) -> int | None:
        """Списать одно занятие с абонемента. None = баланса не было."""
        student = await self.get_student(user_id)
        if not student or int(student.get("lessons_balance") or 0) <= 0:
            return None
        try:
            await self.db.execute(
                "UPDATE students SET lessons_balance = lessons_balance - 1"
                " WHERE user_id = ? AND lessons_balance > 0",
                (user_id,)
            )
            await self.db.commit()
            return int(student["lessons_balance"]) - 1
        except Exception as e:
            logger.error(f"[consume_lesson] Failed: {e}")
            return None

    # =================== ШАБЛОНЫ БЫСТРЫХ ОТВЕТОВ ===================
    async def add_template(self, title: str, text: str) -> int:
        try:
            cursor = await self.db.execute(
                "INSERT INTO reply_templates (title, text) VALUES (?, ?)",
                (title, text)
            )
            await self.db.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            logger.error(f"[add_template] Failed: {e}")
            return 0

    async def get_templates(self) -> list:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM reply_templates ORDER BY id DESC"
            )
            return [dict(r) for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"[get_templates] Failed: {e}")
            return []

    async def delete_template(self, template_id: int) -> None:
        try:
            await self.db.execute(
                "DELETE FROM reply_templates WHERE id = ?", (template_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[delete_template] Failed: {e}")

    # =================== ОТЛОЖЕННЫЕ СООБЩЕНИЯ ===================
    async def schedule_message(self, student_id: int, text: str, send_at: str) -> int:
        try:
            cursor = await self.db.execute(
                "INSERT INTO scheduled_messages (student_id, text, send_at)"
                " VALUES (?, ?, ?)",
                (student_id, text, send_at)
            )
            await self.db.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            logger.error(f"[schedule_message] Failed: {e}")
            return 0

    async def get_due_messages(self, now_iso: str) -> list:
        """Несформированные сообщения, время которых наступило."""
        try:
            cursor = await self.db.execute(
                "SELECT * FROM scheduled_messages WHERE sent = 0 AND send_at <= ?"
                " ORDER BY send_at LIMIT 20",
                (now_iso,)
            )
            return [dict(r) for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"[get_due_messages] Failed: {e}")
            return []

    async def get_pending_scheduled(self) -> list:
        try:
            cursor = await self.db.execute(
                "SELECT sm.*, st.full_name FROM scheduled_messages sm"
                " LEFT JOIN students st ON sm.student_id = st.user_id"
                " WHERE sm.sent = 0 ORDER BY sm.send_at"
            )
            return [dict(r) for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"[get_pending_scheduled] Failed: {e}")
            return []

    async def mark_message_sent(self, message_id: int) -> None:
        try:
            await self.db.execute(
                "UPDATE scheduled_messages SET sent = 1 WHERE id = ?", (message_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[mark_message_sent] Failed: {e}")

    async def delete_scheduled(self, message_id: int) -> None:
        try:
            await self.db.execute(
                "DELETE FROM scheduled_messages WHERE id = ? AND sent = 0",
                (message_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[delete_scheduled] Failed: {e}")

    # =================== МАТЕРИАЛЫ ===================
    async def add_material(self, title: str, file_id: str,
                           subject_id: int = None) -> int:
        try:
            cursor = await self.db.execute(
                "INSERT INTO materials (subject_id, title, file_id) VALUES (?, ?, ?)",
                (subject_id, title, file_id)
            )
            await self.db.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            logger.error(f"[add_material] Failed: {e}")
            return 0

    async def get_materials(self) -> list:
        try:
            cursor = await self.db.execute(
                "SELECT m.*, s.name AS subject_name FROM materials m"
                " LEFT JOIN subjects s ON m.subject_id = s.id"
                " ORDER BY m.id DESC LIMIT 50"
            )
            return [dict(r) for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"[get_materials] Failed: {e}")
            return []

    async def delete_material(self, material_id: int) -> None:
        try:
            await self.db.execute(
                "DELETE FROM materials WHERE id = ?", (material_id,)
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"[delete_material] Failed: {e}")


db = Database()
