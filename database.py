import aiosqlite
import json
from datetime import datetime, date, timedelta
from typing import Optional
import os


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

    async def close(self):
        if self.db:
            await self.db.close()

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
                session_expires TEXT
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
        except Exception:
            return False

    async def get_student(self, user_id: int) -> Optional[dict]:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM students WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception:
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
        except Exception:
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
        except Exception:
            return []

    async def update_student_activity(self, user_id: int):
        try:
            await self.db.execute(
                """UPDATE students SET last_activity = datetime('now')
                   WHERE user_id = ?""",
                (user_id,)
            )
            await self.db.commit()
        except Exception:
            pass

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
        except Exception:
            pass

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
        except Exception:
            return False

    async def authenticate_admin(self, admin_id: int, hours: int = 12):
        try:
            expires = (
                datetime.now() + timedelta(hours=hours)
            ).isoformat()
            await self.db.execute(
                """INSERT OR REPLACE INTO admin_sessions
                   (admin_id, is_authenticated, auth_time, session_expires)
                   VALUES (?, 1, datetime('now'), ?)""",
                (admin_id, expires)
            )
            await self.db.commit()
        except Exception:
            pass

    async def logout_admin(self, admin_id: int):
        try:
            await self.db.execute(
                """UPDATE admin_sessions SET is_authenticated = 0
                   WHERE admin_id = ?""",
                (admin_id,)
            )
            await self.db.commit()
        except Exception:
            pass

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
        except Exception:
            return 0

    async def get_subjects(self, active_only: bool = True) -> list:
        try:
            query = "SELECT * FROM subjects"
            if active_only:
                query += " WHERE is_active = 1"
            cursor = await self.db.execute(query)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    async def get_subject(self, subject_id: int) -> Optional[dict]:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM subjects WHERE id = ?", (subject_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    async def delete_subject(self, subject_id: int):
        try:
            await self.db.execute(
                "UPDATE subjects SET is_active = 0 WHERE id = ?",
                (subject_id,)
            )
            await self.db.commit()
        except Exception:
            pass

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
        except Exception:
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
        except Exception:
            return []

    async def get_slot(self, slot_id: int) -> Optional[dict]:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM time_slots WHERE id = ?", (slot_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    async def block_slot(self, slot_id: int):
        try:
            await self.db.execute(
                "UPDATE time_slots SET is_available = 0 WHERE id = ?",
                (slot_id,)
            )
            await self.db.commit()
        except Exception:
            pass

    async def unblock_slot(self, slot_id: int):
        try:
            await self.db.execute(
                "UPDATE time_slots SET is_available = 1 WHERE id = ?",
                (slot_id,)
            )
            await self.db.commit()
        except Exception:
            pass

    async def get_all_slots_for_date(self, date_str: str) -> list:
        try:
            cursor = await self.db.execute(
                """SELECT * FROM time_slots WHERE date = ?
                   ORDER BY start_time""",
                (date_str,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # =================== БРОНИРОВАНИЯ ===================

    async def create_booking(self, student_id: int, slot_id: int,
                             subject_id: int = None,
                             booking_type: str = "trial") -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO bookings
                   (student_id, slot_id, subject_id,
                    booking_type, status)
                   VALUES (?, ?, ?, ?, 'confirmed')""",
                (student_id, slot_id, subject_id, booking_type)
            )
            await self.block_slot(slot_id)
            await self.db.commit()
            return cursor.lastrowid
        except Exception:
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
        except Exception:
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
        except Exception:
            return []

    async def get_today_bookings(self) -> list:
        try:
            today = date.today().isoformat()
            cursor = await self.db.execute(
                """SELECT b.*, ts.date, ts.start_time, ts.end_time,
                          s.name as subject_name,
                          st.full_name, st.username
                   FROM bookings b
                   LEFT JOIN time_slots ts ON b.slot_id = ts.id
                   LEFT JOIN subjects s ON b.subject_id = s.id
                   LEFT JOIN students st ON b.student_id = st.user_id
                   WHERE ts.date = ? AND b.status = 'confirmed'
                   ORDER BY ts.start_time""",
                (today,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    async def get_upcoming_bookings(self,
                                    minutes_ahead: int = 60) -> list:
        try:
            now = datetime.now()
            today = now.date().isoformat()
            current_time = now.strftime("%H:%M")
            ahead_time = (
                now + timedelta(minutes=minutes_ahead)
            ).strftime("%H:%M")
            cursor = await self.db.execute(
                """SELECT b.*, ts.date, ts.start_time, ts.end_time,
                          s.name as subject_name,
                          st.full_name,
                          st.user_id as student_user_id
                   FROM bookings b
                   LEFT JOIN time_slots ts ON b.slot_id = ts.id
                   LEFT JOIN subjects s ON b.subject_id = s.id
                   LEFT JOIN students st ON b.student_id = st.user_id
                   WHERE ts.date = ?
                   AND ts.start_time BETWEEN ? AND ?
                   AND b.status = 'confirmed'
                   AND b.reminder_sent = 0""",
                (today, current_time, ahead_time)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    async def mark_reminder_sent(self, booking_id: int):
        try:
            await self.db.execute(
                "UPDATE bookings SET reminder_sent = 1 WHERE id = ?",
                (booking_id,)
            )
            await self.db.commit()
        except Exception:
            pass

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
        except Exception:
            pass

    async def complete_booking(self, booking_id: int):
        try:
            await self.db.execute(
                """UPDATE bookings SET status = 'completed'
                   WHERE id = ?""",
                (booking_id,)
            )
            await self.db.commit()
        except Exception:
            pass

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
        except Exception:
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
        except Exception:
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
        except Exception:
            pass

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
        except Exception:
            pass

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
        except Exception:
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
        except Exception:
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
        except Exception:
            pass

    async def get_payment_stats(self, period_days: int = 30) -> dict:
        try:
            cursor = await self.db.execute(
                """SELECT
                    COUNT(*) as total_payments,
                    SUM(CASE WHEN status='paid'
                        THEN amount ELSE 0 END) as total_paid,
                    SUM(CASE WHEN status='pending'
                        THEN amount ELSE 0 END) as total_pending,
                    COUNT(CASE WHEN status='paid'
                        THEN 1 END) as paid_count,
                    COUNT(CASE WHEN status='pending'
                        THEN 1 END) as pending_count
                   FROM payments
                   WHERE created_at >= datetime('now', ?)""",
                (f"-{period_days} days",)
            )
            row = await cursor.fetchone()
            return dict(row) if row else {}
        except Exception:
            return {}

    # =================== ОТЗЫВЫ ===================

    async def add_review(self, student_id: int, rating: int,
                         text: str = "",
                         booking_id: int = None) -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO reviews
                   (student_id, booking_id, rating, text)
                   VALUES (?, ?, ?, ?)""",
                (student_id, booking_id, rating, text)
            )
            await self.db.commit()
            return cursor.lastrowid
        except Exception:
            return 0

    async def get_reviews(self,
                          published_only: bool = False) -> list:
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
        except Exception:
            return []

    async def publish_review(self, review_id: int):
        try:
            await self.db.execute(
                "UPDATE reviews SET is_published = 1 WHERE id = ?",
                (review_id,)
            )
            await self.db.commit()
        except Exception:
            pass

    async def get_average_rating(self) -> float:
        try:
            cursor = await self.db.execute(
                "SELECT AVG(rating) as avg_rating FROM reviews"
            )
            row = await cursor.fetchone()
            val = row["avg_rating"] if row else None
            return round(float(val), 2) if val else 0.0
        except Exception:
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
        except Exception:
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
        except Exception:
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
        except Exception:
            return None

    async def delete_faq(self, faq_id: int):
        try:
            await self.db.execute(
                "UPDATE faq SET is_active = 0 WHERE id = ?",
                (faq_id,)
            )
            await self.db.commit()
        except Exception:
            pass

    # =================== ЧАТЫ ===================

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
        except Exception:
            pass

    async def get_ad_chats(self,
                           active_only: bool = True) -> list:
        try:
            query = "SELECT * FROM ad_chats"
            if active_only:
                query += " WHERE is_active = 1"
            cursor = await self.db.execute(query)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
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
        except Exception:
            pass

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
        except Exception:
            return 0

    async def update_mailing_stats(self, mailing_id: int,
                                   sent: int, errors: int):
        try:
            await self.db.execute(
                """UPDATE mailings SET status = 'sent',
                   sent_at = datetime('now'),
                   total_sent = ?, total_errors = ?
                   WHERE id = ?""",
                (sent, errors, mailing_id)
            )
            await self.db.commit()
        except Exception:
            pass

    async def get_mailings(self, limit: int = 20) -> list:
        try:
            cursor = await self.db.execute(
                """SELECT * FROM mailings
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
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
        except Exception:
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
        except Exception:
            return {"total_referrals": 0, "completed": 0}

    # =================== ВОРОНКА ===================

    async def log_funnel_event(self, user_id: int,
                               event_type: str,
                               source: str = None,
                               source_chat_id: int = None,
                               metadata: dict = None):
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
        except Exception:
            pass

    async def get_funnel_stats(self,
                               period_days: int = 30) -> dict:
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
        except Exception:
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
        except Exception:
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
        except Exception:
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
        except Exception:
            pass

    # =================== DND ===================

    async def add_dnd_schedule(self, start_time: str,
                               end_time: str,
                               day_of_week: int = None,
                               auto_reply: str = None):
        try:
            await self.db.execute(
                """INSERT INTO dnd_schedule
                   (day_of_week, start_time, end_time,
                    auto_reply_text)
                   VALUES (?, ?, ?, ?)""",
                (day_of_week, start_time, end_time,
                 auto_reply or
                 "Сейчас идёт занятие. Отвечу позже!")
            )
            await self.db.commit()
        except Exception:
            pass

    async def clear_dnd_schedules(self):
        try:
            await self.db.execute("DELETE FROM dnd_schedule")
            await self.db.commit()
        except Exception:
            pass

    async def is_dnd_active(self) -> tuple:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_day = now.weekday()
            cursor = await self.db.execute(
                """SELECT auto_reply_text FROM dnd_schedule
                   WHERE (day_of_week IS NULL OR day_of_week = ?)
                   AND start_time <= ? AND end_time >= ?""",
                (current_day, current_time, current_time)
            )
            row = await cursor.fetchone()
            if row:
                return True, row["auto_reply_text"]
            return False, ""
        except Exception:
            return False, ""

    # =================== A/B ТЕСТЫ ===================

    async def create_ab_test(self, name: str,
                             variant_a: str,
                             variant_b: str) -> int:
        try:
            cursor = await self.db.execute(
                """INSERT INTO ab_tests
                   (name, variant_a_text, variant_b_text)
                   VALUES (?, ?, ?)""",
                (name, variant_a, variant_b)
            )
            await self.db.commit()
            return cursor.lastrowid
        except Exception:
            return 0

    async def get_active_ab_tests(self) -> list:
        try:
            cursor = await self.db.execute(
                "SELECT * FROM ab_tests WHERE status = 'active'"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    async def increment_ab_stat(self, test_id: int,
                                variant: str,
                                stat: str = "sends"):
        try:
            col = f"variant_{variant.lower()}_{stat}"
            await self.db.execute(
                f"""UPDATE ab_tests
                    SET {col} = {col} + 1
                    WHERE id = ?""",
                (test_id,)
            )
            await self.db.commit()
        except Exception:
            pass

    # =================== ЛОГИ ===================

    async def log_action(self, user_id: int, action: str,
                         details: dict = None):
        try:
            await self.db.execute(
                """INSERT INTO action_logs
                   (user_id, action, details)
                   VALUES (?, ?, ?)""",
                (user_id, action, json.dumps(details or {}))
            )
            await self.db.commit()
        except Exception:
            pass

    # =================== ДАШБОРД ===================

    async def get_dashboard_stats(self) -> dict:
        stats = {
            "total_students": 0,
            "new_students_month": 0,
            "today_bookings": 0,
            "trial_bookings_month": 0,
            "trial_conversion": 0,
            "avg_rating": 0.0,
            "revenue_month": 0,
            "pending_payments": 0,
            "funnel": {}
        }
        try:
            cursor = await self.db.execute(
                """SELECT COUNT(*) as c FROM students
                   WHERE is_active = 1"""
            )
            row = await cursor.fetchone()
            stats["total_students"] = row["c"] if row else 0

            cursor = await self.db.execute(
                """SELECT COUNT(*) as c FROM students
                   WHERE registration_date >=
                       datetime('now', '-30 days')"""
            )
            row = await cursor.fetchone()
            stats["new_students_month"] = row["c"] if row else 0

            today = date.today().isoformat()
            cursor = await self.db.execute(
                """SELECT COUNT(*) as c FROM bookings b
                   LEFT JOIN time_slots ts ON b.slot_id = ts.id
                   WHERE ts.date = ?
                   AND b.status = 'confirmed'""",
                (today,)
            )
            row = await cursor.fetchone()
            stats["today_bookings"] = row["c"] if row else 0

            cursor = await self.db.execute(
                """SELECT COUNT(*) as c FROM bookings
                   WHERE booking_type = 'trial'
                   AND created_at >= datetime('now', '-30 days')"""
            )
            row = await cursor.fetchone()
            stats["trial_bookings_month"] = row["c"] if row else 0

            cursor = await self.db.execute(
                """SELECT
                    COUNT(CASE WHEN booking_type='trial'
                        THEN 1 END) as trials,
                    COUNT(CASE WHEN booking_type='regular'
                        THEN 1 END) as regulars
                   FROM bookings
                   WHERE created_at >= datetime('now', '-30 days')
                   AND status != 'cancelled'"""
            )
            row = await cursor.fetchone()
            if row:
                trials = row["trials"] or 0
                regulars = row["regulars"] or 0
                stats["trial_conversion"] = (
                    round(regulars / trials * 100, 1)
                    if trials > 0 else 0
                )

            stats["avg_rating"] = await self.get_average_rating()

            payment_stats = await self.get_payment_stats(30)
            stats["revenue_month"] = (
                payment_stats.get("total_paid", 0) or 0
            )
            stats["pending_payments"] = (
                payment_stats.get("total_pending", 0) or 0
            )
            stats["funnel"] = await self.get_funnel_stats(30)

        except Exception:
            pass

        return stats


# Глобальный экземпляр
db = Database()