from sqlalchemy.orm import Session

from app.engines.base import AIEngine
from app.engines.claude_engine import ClaudeAdapter
from app.engines.openai_engine import OpenAIAdapter
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.security.crypto import decrypt_key

# The hotel whose key backs the public nahariya website (see
# NAHARIYA_GUIDE_HOTEL_ID in app/ui/routes.py) — reused as the fallback key
# for any hotel registered without its own api_key (HotelUpsertRequest.api_key
# in app/api/chat.py left blank).
DEFAULT_API_KEY_HOTEL_ID = "nahariya-guide"


class UnknownHotelError(LookupError):
    pass


def get_engine(hotel_id: str, db: Session) -> AIEngine:
    """Return the configured AI engine for a hotel, with its decrypted API key.

    Falls back to DEFAULT_API_KEY_HOTEL_ID's key when this hotel has none of
    its own.
    """
    row = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
    if row is None:
        raise UnknownHotelError(hotel_id)
    api_key = decrypt_key(row.api_key_encrypted) if row.api_key_encrypted else None
    if api_key is None and hotel_id != DEFAULT_API_KEY_HOTEL_ID:
        default_row = (
            db.query(HotelSettings).filter_by(hotel_id=DEFAULT_API_KEY_HOTEL_ID).one_or_none()
        )
        if default_row is not None and default_row.api_key_encrypted:
            api_key = decrypt_key(default_row.api_key_encrypted)
    if row.ai_engine == AIEngineType.claude:
        return ClaudeAdapter(api_key=api_key or "")
    return OpenAIAdapter(api_key=api_key or "")
