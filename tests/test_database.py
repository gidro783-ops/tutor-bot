# -*- coding: utf-8 -*-
"""Тесты database.py на реальной SQLite (свежий файл на каждый тест)."""
from datetime import date

from async_runner import run

TODAY = date.today().isoformat()
TOMORROW = date.fromordinal(date.today().toordinal() + 1).isoformat()


class TestStudents:
    def test_add_and_get(self, db):
        assert run(db.add_student(100, "Иван Тестов", username="@ivan"))
        student = run(db.get_student(100))
        assert student is not None
        assert student["full_name"] == "Иван Тестов"
        assert student["username"] == "@ivan"

    def test_duplicate_user_id_ignored(self, db):
        run(db.add_student(100, "Первый"))
        run(db.add_student(100, "Второй"))
        students = run(db.get_all_students())
        assert len(students) == 1
        assert students[0]["full_name"] == "Первый"

    def test_update_student(self, db):
        run(db.add_student(100, "Иван"))
        run(db.update_student(100, notes="Занимается алгеброй"))
        student = run(db.get_student(100))
        assert student["notes"] == "Занимается алгеброй"

    def test_get_missing_student(self, db):
        assert run(db.get_student(999999)) is None


class TestAdminSession:
    def test_auth_and_logout(self, db):
        run(db.authenticate_admin(1, hours=12))
        assert run(db.check_admin_session(1))
        run(db.logout_admin(1))
        assert not run(db.check_admin_session(1))

    def test_expired_session_rejected(self, db):
        run(db.authenticate_admin(1, hours=-1))  # уже истекла
        assert not run(db.check_admin_session(1))

    def test_unknown_admin_rejected(self, db):
        assert not run(db.check_admin_session(42))


class TestSubjects:
    def test_add_list_delete(self, db):
        subject_id = run(db.add_subject("Алгебра", 1200, "Школьный курс"))
        assert subject_id > 0
        names = [s["name"] for s in run(db.get_subjects())]
        assert "Алгебра" in names

        run(db.delete_subject(subject_id))
        names = [s["name"] for s in run(db.get_subjects())]
        assert "Алгебра" not in names

    def test_duplicate_name_rejected(self, db):
        assert run(db.add_subject("Физика", 1000)) > 0
        assert run(db.add_subject("Физика", 1500)) == 0


class TestSlotsAndBookings:
    def _make_slot(self, db, day=TODAY):
        return run(db.add_time_slot(day, "10:00", "11:00"))

    def test_booking_blocks_slot(self, db):
        run(db.add_student(100, "Иван"))
        slot_id = self._make_slot(db)
        booking_id = run(db.create_booking(100, slot_id, booking_type="trial"))
        assert booking_id > 0

        booked = {s["id"] for s in run(db.get_available_slots(from_date=TODAY))}
        assert slot_id not in booked

    def test_cancel_frees_slot(self, db):
        run(db.add_student(100, "Иван"))
        slot_id = self._make_slot(db)
        booking_id = run(db.create_booking(100, slot_id))
        run(db.cancel_booking(booking_id, reason="тест"))

        booking = run(db.get_booking(booking_id))
        assert booking["status"] == "cancelled"
        available = {s["id"] for s in run(db.get_available_slots(from_date=TODAY))}
        assert slot_id in available

    def test_duplicate_slot_ignored(self, db):
        first = self._make_slot(db)
        assert first > 0
        # повторная вставка того же дня/времени не создаёт вторую строку
        self._make_slot(db)
        slots = run(db.get_slots_for_date(TODAY))
        assert len([s for s in slots if s["start_time"] == "10:00"]) == 1

    def test_student_sees_own_bookings(self, db):
        run(db.add_student(100, "Иван"))
        slot_id = self._make_slot(db)
        booking_id = run(db.create_booking(100, slot_id))
        ids = [b["id"] for b in run(db.get_student_bookings(100))]
        assert booking_id in ids


class TestPayments:
    def test_lifecycle_pending_reported_paid(self, db):
        run(db.add_student(100, "Иван"))
        pay_id = run(db.create_payment(100, 2500, "8 занятий"))
        assert pay_id > 0
        assert any(p["id"] == pay_id for p in run(db.get_pending_payments()))

        # «Я оплатил» → reported, повторное нажатие не срабатывает
        assert run(db.report_payment_paid(pay_id))
        assert not run(db.report_payment_paid(pay_id))
        assert not any(p["id"] == pay_id for p in run(db.get_pending_payments()))

        run(db.confirm_payment(pay_id))
        payment = run(db.get_payment_by_id(pay_id))
        assert payment["status"] == "paid"


class TestHomework:
    def test_due_tomorrow_reminders(self, db):
        run(db.add_student(100, "Иван"))
        due_id = run(db.add_homework(100, "ДР на завтра", due_date=TOMORROW))
        run(db.add_homework(100, "ДР на послезавтра",
                            due_date=date.fromordinal(date.today().toordinal() + 2).isoformat()))
        submitted = run(db.add_homework(100, "Сданное", due_date=TOMORROW))
        run(db.submit_homework(submitted))

        due = run(db.get_homework_due(TOMORROW))
        ids = [h["id"] for h in due]
        assert due_id in ids                    # дедлайн завтра, не сдано
        assert submitted not in ids             # сданное не напоминаем
        assert len([i for i in ids]) == 1       # послезавтрашнее не попало
        assert due[0]["full_name"] == "Иван"    # имя для логов репетитора

    def test_assign_submit_grade(self, db):
        run(db.add_student(100, "Иван"))
        hw_id = run(db.add_homework(100, "ДР №5", due_date=TOMORROW))
        assert hw_id > 0
        # выдано, но ещё не сдано → на проверке нет
        assert not any(h["id"] == hw_id for h in run(db.get_pending_homework()))

        run(db.submit_homework(hw_id))
        assert any(h["id"] == hw_id for h in run(db.get_pending_homework()))

        run(db.grade_homework(hw_id, "5", "Отлично!"))
        homework = run(db.get_homework_by_id(hw_id))
        assert homework["status"] == "graded"
        assert homework["grade"] == "5"
        assert not any(h["id"] == hw_id for h in run(db.get_pending_homework()))


class TestSettings:
    def test_set_get(self, db):
        run(db.set_setting("greeting", "Привет!"))
        assert run(db.get_setting("greeting")) == "Привет!"

    def test_default_for_missing(self, db):
        assert run(db.get_setting("no_such_key", "fallback")) == "fallback"

    def test_dnd_toggle(self, db):
        run(db.set_dnd(True))
        assert run(db.get_setting("dnd_enabled")) == "1"
        run(db.set_dnd(False))
        assert run(db.get_setting("dnd_enabled")) == "0"


class TestAdChats:
    def test_add_and_leads(self, db):
        run(db.add_ad_chat(-100123, "Канал репетиторов"))
        chats = run(db.get_ad_chats())
        assert any(c["chat_id"] == -100123 for c in chats)

        run(db.increment_chat_leads(-100123))
        chats = run(db.get_ad_chats())
        target = next(c for c in chats if c["chat_id"] == -100123)
        assert target["total_leads"] == 1


class TestNewFeatures:
    def test_templates_crud(self, db):
        tid = run(db.add_template("Напоминание", "Привет, {name}!"))
        assert tid > 0
        items = run(db.get_templates())
        assert any(t["id"] == tid for t in items)
        run(db.delete_template(tid))
        assert not any(t["id"] == tid for t in run(db.get_templates()))

    def test_scheduled_messages(self, db):
        run(db.add_student(100, "Иван"))
        mid = run(db.schedule_message(100, "Не забудь занятие", "2020-01-01 10:00"))
        assert mid > 0
        due = run(db.get_due_messages("2020-01-01 10:00"))
        assert any(m["id"] == mid for m in due)
        run(db.mark_message_sent(mid))
        assert not any(m["id"] == mid for m in run(db.get_due_messages("2099-01-01 00:00")))

    def test_materials(self, db):
        mid = run(db.add_material("Конспект", "file_id_123"))
        assert mid > 0
        items = run(db.get_materials())
        assert any(m["id"] == mid and m["file_id"] == "file_id_123" for m in items)
        run(db.delete_material(mid))
        assert not run(db.get_materials())
