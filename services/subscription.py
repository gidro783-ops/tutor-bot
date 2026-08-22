"""Подписки tutor-bot с защитой от блокировок SQLite (WAL mode + busy_timeout)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

import aiosqlite

from config import config

logger = logging.getLogger(__name__)
TRIAL_DAYS = 7


class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"
    WHITE_LABEL = "white_label"


@dataclass(frozen=True)
class PlanInfo:
    code: Plan
    title: str
    price_rub: int
    max_students: int | None
    homework: bool
    analytics: bool
    mailing: bool
    white_label: bool
    # Лимиты Free-тарифа (None = безлимит на платных)
    max_mailing_per_day: int | None = None
    max_homework_per_month: int | None = None


PLANS: dict[Plan, PlanInfo] = {
    Plan.FREE: PlanInfo(
        Plan.FREE, "Free", 0, 5,
        homework=True, analytics=False, mailing=True, white_label=False,
        max_mailing_per_day=10, max_homework_per_month=5,
    ),
    Plan.PRO: PlanInfo(Plan.PRO, "PRO", 990, None, True, True, True, False),
    Plan.WHITE_LABEL: PlanInfo(
        Plan.WHITE_LABEL, "White Label", 3990, None, True, True, True, True
    ),
}

PRO_PRICE_RUB = PLANS[Plan.PRO].price_rub
WHITE_LABEL_PRICE_RUB = PLANS[Plan.WHITE_LABEL].price_rub


async def _connect() -> aiosqlite.Connection:
    """WAL-режим: чтение и запись одновременно, без 'database is locked'.

    ИСПРАВЛЕНО: соединение создаётся через await и закрывается явно
    (finally). Прежний паттерн `async with await aiosqlite.connect()`
    стартовал поток соединения дважды — RuntimeError «threads can only
    be started once» при первом же вызове.
    """
    conn = await aiosqlite.connect(config.DATABASE_PATH, timeout=10.0)
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA busy_timeout=5000;")
    return conn


async def init_db() -> None:
    conn = await _connect()
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                tutor_id    INTEGER PRIMARY KEY,
                plan        TEXT    NOT NULL DEFAULT 'free',
                expires_at  TEXT,
                brand_name  TEXT,
                brand_about TEXT,
                trial_used  INTEGER NOT NULL DEFAULT 0,
                updated_at  TEXT    NOT NULL
            )
            """
        )
        cur = await conn.execute("PRAGMA table_info(subscriptions)")
        cols = {r[1] for r in await cur.fetchall()}
        if "trial_used" not in cols:
            await conn.execute("ALTER TABLE subscriptions ADD COLUMN trial_used INTEGER NOT NULL DEFAULT 0")
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_counters (
                tutor_id   INTEGER NOT NULL,
                day        TEXT    NOT NULL,
                mails_sent INTEGER NOT NULL DEFAULT 0,
                hw_created INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (tutor_id, day)
            )
            """
        )
        await conn.commit()
    finally:
        await conn.close()


@dataclass
class Subscription:
    tutor_id: int
    plan: Plan
    expires_at: datetime | None
    brand_name: str | None
    brand_about: str | None
    trial_used: bool = False

    @property
    def info(self) -> PlanInfo:
        return PLANS[self.plan]

    @property
    def is_active(self) -> bool:
        if self.plan == Plan.FREE:
            return True
        return self.expires_at is not None and self.expires_at > datetime.now()

    @property
    def effective_info(self) -> PlanInfo:
        if self.plan != Plan.FREE and not self.is_active:
            return PLANS[Plan.FREE]
        return self.info

    @property
    def days_left(self) -> int | None:
        if self.plan == Plan.FREE or self.expires_at is None:
            return None
        return max(0, (self.expires_at - datetime.now()).days)

    @property
    def is_trial(self) -> bool:
        return self.plan == Plan.PRO and self.is_active and self.trial_used and self.expires_at is not None


async def get_subscription(tutor_id: int) -> Subscription:
    conn = await _connect()
    try:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM subscriptions WHERE tutor_id = ?", (tutor_id,)
        )
        row = await cur.fetchone()
    finally:
        await conn.close()
    if row is None:
        return Subscription(tutor_id, Plan.FREE, None, None, None, False)
    expires = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
    return Subscription(
        row["tutor_id"], Plan(row["plan"]), expires,
        row["brand_name"], row["brand_about"], bool(row["trial_used"]),
    )


async def start_trial(tutor_id: int) -> Subscription | None:
    sub = await get_subscription(tutor_id)
    if sub.trial_used:
        return None
    if sub.plan != Plan.FREE and sub.is_active:
        return None
    expires = datetime.now() + timedelta(days=TRIAL_DAYS)
    conn = await _connect()
    try:
        await conn.execute(
            """
            INSERT INTO subscriptions (tutor_id, plan, expires_at, trial_used, updated_at)
            VALUES (?, 'pro', ?, 1, ?)
            ON CONFLICT(tutor_id) DO UPDATE SET
                plan='pro', expires_at=excluded.expires_at,
                trial_used=1, updated_at=excluded.updated_at
            """,
            (tutor_id, expires.isoformat(), datetime.now().isoformat()),
        )
        await conn.commit()
    finally:
        await conn.close()
    logger.info("Trial PRO %sd granted to %s until %s", TRIAL_DAYS, tutor_id, expires)
    return await get_subscription(tutor_id)


async def activate(tutor_id: int, plan: Plan, months: int = 1) -> Subscription:
    current = await get_subscription(tutor_id)
    base = current.expires_at if (current.expires_at and current.expires_at > datetime.now()) else datetime.now()
    expires = base + timedelta(days=30 * months)
    conn = await _connect()
    try:
        await conn.execute(
            """
            INSERT INTO subscriptions (tutor_id, plan, expires_at, trial_used, updated_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(tutor_id) DO UPDATE SET
                plan=excluded.plan, expires_at=excluded.expires_at,
                trial_used=1, updated_at=excluded.updated_at
            """,
            (tutor_id, plan.value, expires.isoformat(), datetime.now().isoformat()),
        )
        await conn.commit()
    finally:
        await conn.close()
    logger.info("Subscription %s active for %s until %s", plan.value, tutor_id, expires)
    return await get_subscription(tutor_id)


async def set_brand(tutor_id: int, name: str | None, about: str | None) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            "UPDATE subscriptions SET brand_name=?, brand_about=?, updated_at=? WHERE tutor_id=?",
            (name, about, datetime.now().isoformat(), tutor_id),
        )
        await conn.commit()
    finally:
        await conn.close()


async def can_add_student(tutor_id: int, current_count: int) -> bool:
    sub = await get_subscription(tutor_id)
    limit = sub.effective_info.max_students
    return True if limit is None else current_count < limit


async def feature_enabled(tutor_id: int, feature: str) -> bool:
    sub = await get_subscription(tutor_id)
    return bool(getattr(sub.effective_info, feature, False))


# =================== КВОТЫ (лимиты Free: рассылки и ДЗ) ===================

def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _month_prefix() -> str:
    return datetime.now().strftime("%Y-%m")


async def _get_usage_row(conn: aiosqlite.Connection, tutor_id: int) -> tuple:
    cur = await conn.execute(
        "SELECT mails_sent, hw_created FROM usage_counters WHERE tutor_id=? AND day=?",
        (tutor_id, _today()),
    )
    row = await cur.fetchone()
    return row if row else (0, 0)


async def get_usage(tutor_id: int) -> dict:
    """Сколько сегодня отправлено рассылок и создано ДЗ в этом месяце."""
    conn = await _connect()
    try:
        mails_today, _ = await _get_usage_row(conn, tutor_id)
        cur = await conn.execute(
            """SELECT COALESCE(SUM(hw_created), 0) FROM usage_counters
               WHERE tutor_id=? AND day LIKE ?""",
            (tutor_id, _month_prefix() + "%"),
        )
        hw_month = (await cur.fetchone())[0]
        return {"mails_today": mails_today, "hw_month": hw_month}
    finally:
        await conn.close()


async def mailing_left_today(tutor_id: int) -> int | None:
    """None — безлимит; иначе сколько сообщений рассылки ещё можно сегодня."""
    sub = await get_subscription(tutor_id)
    limit = sub.effective_info.max_mailing_per_day
    if limit is None:
        return None
    usage = await get_usage(tutor_id)
    return max(0, limit - usage["mails_today"])


async def can_send_mailing(tutor_id: int, count: int) -> bool:
    left = await mailing_left_today(tutor_id)
    return left is None or count <= left


async def consume_mailing(tutor_id: int, n: int) -> None:
    if n <= 0:
        return
    conn = await _connect()
    try:
        await conn.execute(
            """
            INSERT INTO usage_counters (tutor_id, day, mails_sent, hw_created)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(tutor_id, day) DO UPDATE SET
                mails_sent = mails_sent + excluded.mails_sent
            """,
            (tutor_id, _today(), n),
        )
        await conn.commit()
    finally:
        await conn.close()


async def homework_left_this_month(tutor_id: int) -> int | None:
    sub = await get_subscription(tutor_id)
    limit = sub.effective_info.max_homework_per_month
    if limit is None:
        return None
    usage = await get_usage(tutor_id)
    return max(0, limit - usage["hw_month"])


async def consume_homework(tutor_id: int) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            """
            INSERT INTO usage_counters (tutor_id, day, mails_sent, hw_created)
            VALUES (?, ?, 0, 1)
            ON CONFLICT(tutor_id, day) DO UPDATE SET
                hw_created = hw_created + 1
            """,
            (tutor_id, _today()),
        )
        await conn.commit()
    finally:
        await conn.close()
