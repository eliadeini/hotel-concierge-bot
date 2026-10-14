import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Only these two for now — adding a third language later means extending
# this set, the admin validator in app/api/chat.py, and (for a genuinely
# correct rendering, not just translated text) the template's RTL-authored
# CSS, which currently assumes Hebrew/RTL regardless of which language is
# actually shown. See app/ui/README.md.
SUPPORTED_LANGUAGES = {"he", "en"}
DEFAULT_LANGUAGE = "he"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def pick_language(localized_json: str, lang: str) -> str:
    """Parses a {"he": "...", "en": "..."} JSON string (as stored in
    display_name/tagline/page_title below) and returns the requested
    language's text, falling back to Hebrew if that language wasn't
    provided for this particular field (he is always required — see
    app/api/chat.py's admin validation — so this fallback can never miss)."""
    data = json.loads(localized_json)
    return data.get(lang) or data["he"]


class HotelWebPage(Base):
    """A hotel's generic branded browser chat page — one-to-one with
    HotelSettings, served at /chatbot/{location}/{slug} (see
    app/ui/routes.py). No hotel-specific name/text/image ever lives in this
    table's code — only in the row's data and the gitignored image files
    under app/ui/hotel_assets/<hotel_id>/ (see that folder's README.md).
    """

    __tablename__ = "hotel_web_page"
    __table_args__ = (
        UniqueConstraint("location", "slug", name="uq_hotel_web_page_location_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_settings_id: Mapped[int] = mapped_column(
        ForeignKey("hotel_settings.id", ondelete="CASCADE"), unique=True, index=True
    )

    # Together form the URL /chatbot/<location>/<slug> — both lowercase,
    # URL-safe (validated in app/api/chat.py's admin endpoint).
    location: Mapped[str] = mapped_column(String(64))
    slug: Mapped[str] = mapped_column(String(64))

    # Each of these three stores a JSON object, e.g. {"he": "...", "en":
    # "..."} — not plain text. "he" is always required (enforced by the
    # admin request validation in app/api/chat.py, not by the DB); "en" is
    # optional, missing it just means pick_language() falls back to "he"
    # for that field when ?lang=en is requested. Parse with pick_language(),
    # never read these columns directly.
    display_name: Mapped[str] = mapped_column(String(256))
    tagline: Mapped[str] = mapped_column(String(1024))
    page_title: Mapped[str] = mapped_column(String(256))

    # Plain file names only (no path), resolved at render time to
    # /hotel-assets/<hotel_id>/<file> — see app/ui/hotel_assets/README.md.
    logo_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    background_file: Mapped[str | None] = mapped_column(String(255), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    hotel: Mapped["HotelSettings"] = relationship(back_populates="web_page")  # noqa: F821
