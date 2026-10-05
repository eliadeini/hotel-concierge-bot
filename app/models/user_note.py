import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UserNoteStatus(str, enum.Enum):
    new = "new"
    reviewed = "reviewed"


class UserNoteSentiment(str, enum.Enum):
    like = "like"
    dislike = "dislike"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserNote(Base):
    """A guest's reaction to a specific logged exchange — a quick
    like/dislike, a free-text note (disagreement or suggestion), or both.
    See app/user_notes.py for how these get created. Reviewed manually via
    GET /admin/notes for now."""

    __tablename__ = "user_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_log_id: Mapped[int] = mapped_column(
        ForeignKey("conversation_log.id", ondelete="CASCADE"), index=True
    )
    # "website" today — exists from day one so a future WhatsApp note trigger
    # (see app/user_notes.py::submit_user_note) needs no schema change.
    channel: Mapped[str] = mapped_column(String(32))
    sentiment: Mapped[UserNoteSentiment | None] = mapped_column(
        Enum(UserNoteSentiment, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[UserNoteStatus] = mapped_column(
        Enum(UserNoteStatus, values_callable=lambda e: [m.value for m in e]),
        default=UserNoteStatus.new,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversation: Mapped["ConversationLog"] = relationship()  # noqa: F821
