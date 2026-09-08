import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MessagingProviderType(str, enum.Enum):
    twilio = "twilio"
    meta_direct = "meta_direct"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HotelMessagingSettings(Base):
    """Per-hotel WhatsApp messaging config. One-to-one with HotelSettings.

    Any field left unset here falls back to the global default in
    app/config.py (see app/messaging/factory.py) — a hotel only needs a row
    here to override the global provider/credentials.
    """

    __tablename__ = "hotel_messaging_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_settings_id: Mapped[int] = mapped_column(
        ForeignKey("hotel_settings.id", ondelete="CASCADE"), unique=True, index=True
    )

    # None = inherit the global default provider.
    provider: Mapped[MessagingProviderType | None] = mapped_column(
        Enum(MessagingProviderType, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )

    twilio_account_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    twilio_auth_token_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    twilio_whatsapp_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    meta_phone_number_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta_access_token_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Overrides settings.whatsapp_daily_limit_per_hotel for this hotel only.
    daily_message_limit_override: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    hotel: Mapped["HotelSettings"] = relationship(back_populates="messaging")  # noqa: F821