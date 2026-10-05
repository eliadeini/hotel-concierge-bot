"""Guest reactions (like/dislike, free-text notes) to a specific logged
exchange — shared by every channel's submission path. Today only the
website calls this (see app/ui/routes.py); a future WhatsApp trigger (no
buttons there, so it'd need a recognized reply pattern in
app/messaging/inbound.py/flow.py) would call the same function with
channel="whatsapp", so the storage layer never needs channel-specific logic.
"""

from sqlalchemy.orm import Session

from app.models.conversation_log import ConversationLog
from app.models.user_note import UserNote, UserNoteSentiment


def submit_user_note(
    conversation_id: int,
    channel: str,
    db: Session,
    message: str | None = None,
    sentiment: UserNoteSentiment | None = None,
) -> UserNote:
    """Raises ValueError for an unknown conversation_id."""
    conversation = db.query(ConversationLog).filter_by(id=conversation_id).one_or_none()
    if conversation is None:
        raise ValueError(f"Unknown conversation_id: {conversation_id}")

    note = UserNote(
        conversation_log_id=conversation_id,
        channel=channel,
        message=message,
        sentiment=sentiment,
    )
    db.add(note)
    db.commit()
    return note
