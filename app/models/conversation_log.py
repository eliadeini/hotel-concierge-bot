from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationLog(Base):
    """Anonymous conversation log — no guest identifiers of any kind."""

    __tablename__ = "conversation_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[str] = mapped_column(String(64), index=True)
    region: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    found_in_kb: Mapped[bool] = mapped_column(Boolean)
    ai_engine: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
