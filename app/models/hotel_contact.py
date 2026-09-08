from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HotelContact(Base):
    __tablename__ = "hotel_contact"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Foreign key → the hotel this person belongs to.
    hotel_settings_id: Mapped[int] = mapped_column(
        ForeignKey("hotel_settings.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Order in which contacts are asked to fill knowledge-base gaps (see the
    # phase 2 reception-feedback loop in hotel_concierge_bot_plan.md) —
    # lower number is asked first. Not unique; ties are broken arbitrarily.
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # ORM navigation: contact.hotel → the HotelSettings row.
    hotel: Mapped["HotelSettings"] = relationship(back_populates="contacts")  # noqa: F821