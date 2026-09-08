import enum
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GuestFlowState(str, enum.Enum):
    awaiting_help_confirmation = "awaiting_help_confirmation"
    awaiting_trip_type = "awaiting_trip_type"


class TripType(str, enum.Enum):
    vacation = "vacation"
    business = "business"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GuestSession(Base):
    """A guest's current stay — phone number + vacation info only, per the
    PII-minimization principle in hotel_concierge_bot_plan.md. No name, no
    ID, nothing that identifies the guest as a person. Auto-deleted at
    checkout via scripts/purge_expired_guest_sessions.py, not stored
    permanently.
    """

    __tablename__ = "guest_session"
    __table_args__ = (
        UniqueConstraint("hotel_settings_id", "phone", name="uq_guest_session_hotel_phone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_settings_id: Mapped[int] = mapped_column(
        ForeignKey("hotel_settings.id", ondelete="CASCADE"), index=True
    )
    # No "whatsapp:" prefix stored — matches the from_number convention in
    # app/api/whatsapp_webhook.py.
    phone: Mapped[str] = mapped_column(String(32), index=True)
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date | None] = mapped_column(Date, nullable=True)
    welcome_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    flow_state: Mapped[GuestFlowState | None] = mapped_column(
        Enum(GuestFlowState, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    trip_type: Mapped[TripType | None] = mapped_column(
        Enum(TripType, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    hotel: Mapped["HotelSettings"] = relationship(back_populates="guest_sessions")  # noqa: F821