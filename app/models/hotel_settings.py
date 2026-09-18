import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AIEngineType(str, enum.Enum):
    openai = "openai"
    claude = "claude"


class PresentationMode(str, enum.Enum):
    # A real, live hotel (e.g. H34 once it's back in production) — shared
    # knowledge content is used as-is; landmark references to this hotel
    # are correct since the tenant IS that business.
    hotel = "hotel"
    # The WhatsApp-lookalike hotel demo (GET /demo), for showing
    # prospective hotel clients what the product looks like — same
    # as-is treatment as "hotel" above, just a separate tenant/id.
    hotel_demo = "hotel-demo"
    # A general-purpose public tenant (e.g. the /chatbot/<location> sites)
    # — shared knowledge content is passed through a neutralization step
    # (see app/messaging/inbound.py::gather_context) so it doesn't surface
    # a specific hotel's name/landmark to anonymous public visitors.
    website = "website"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HotelSettings(Base):
    __tablename__ = "hotel_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ai_engine: Mapped[AIEngineType] = mapped_column(
        Enum(AIEngineType, values_callable=lambda e: [m.value for m in e])
    )
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    # Test hotels (e.g. the prague manual-test region) must never be exposed
    # to real end users.
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    # Path to a git-tracked Markdown file with this hotel's free-text
    # "skill" — tone/branding instructions and the WhatsApp onboarding
    # greeting (see app/knowledge/hotel_skill.py). Read fresh on every
    # request, like the region knowledge files; None means use the generic
    # defaults in app/messaging/templates.py.
    hotel_skill_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Controls how shared knowledge-base content is presented for this
    # tenant — see PresentationMode above. Defaults to "hotel" so every
    # existing/future real-hotel tenant is unaffected unless explicitly
    # set otherwise.
    presentation_mode: Mapped[PresentationMode] = mapped_column(
        Enum(PresentationMode, values_callable=lambda e: [m.value for m in e]),
        default=PresentationMode.hotel,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # One hotel → many contacts. Not a column; ORM navigation only.
    contacts: Mapped[list["HotelContact"]] = relationship(  # noqa: F821
        back_populates="hotel",
        cascade="all, delete-orphan",
    )

    region_tags: Mapped[list["HotelRegionTag"]] = relationship(  # noqa: F821
        back_populates="hotel",
        cascade="all, delete-orphan",
    )

    messaging: Mapped["HotelMessagingSettings | None"] = relationship(  # noqa: F821
        back_populates="hotel",
        uselist=False,
        cascade="all, delete-orphan",
    )

    guest_sessions: Mapped[list["GuestSession"]] = relationship(  # noqa: F821
        back_populates="hotel",
        cascade="all, delete-orphan",
    )
