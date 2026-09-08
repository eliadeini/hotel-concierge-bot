from sqlalchemy.orm import Session

from app.engines.base import AIEngine
from app.engines.claude_engine import ClaudeAdapter
from app.engines.openai_engine import OpenAIAdapter
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.security.crypto import decrypt_key


class UnknownHotelError(LookupError):
    pass


def get_engine(hotel_id: str, db: Session) -> AIEngine:
    """Return the configured AI engine for a hotel, with its decrypted API key."""
    row = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
    if row is None:
        raise UnknownHotelError(hotel_id)
    api_key = decrypt_key(row.api_key_encrypted)
    if row.ai_engine == AIEngineType.claude:
        return ClaudeAdapter(api_key=api_key)
    return OpenAIAdapter(api_key=api_key)
