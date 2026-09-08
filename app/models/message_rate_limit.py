import enum
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RateLimitScope(str, enum.Enum):
    phone = "phone"
    hotel = "hotel"
    global_ = "global"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessageRateLimitCounter(Base):
    """One row per (scope, scope_key, day) — how many WhatsApp sends have
    happened today for that phone number / hotel / the whole app.

    Only "today's" row matters for enforcement; older rows are harmless and
    can be pruned later. No FK to scope_key on purpose — it's a phone
    number, a hotel_id, or the literal string "global" depending on scope,
    not a single table's primary key.
    """

    __tablename__ = "message_rate_limit_counter"
    __table_args__ = (
        UniqueConstraint("scope", "scope_key", "day", name="uq_message_rate_limit_counter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[RateLimitScope] = mapped_column(
        Enum(RateLimitScope, values_callable=lambda e: [m.value for m in e])
    )
    scope_key: Mapped[str] = mapped_column(String(64), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )