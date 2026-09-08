import pytest

from app.engines.claude_engine import ClaudeAdapter
from app.engines.factory import UnknownHotelError, get_engine
from app.engines.openai_engine import OpenAIAdapter
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.security.crypto import encrypt_key


def add_hotel(db, hotel_id, engine_type):
    db.add(
        HotelSettings(
            hotel_id=hotel_id,
            ai_engine=engine_type,
            api_key_encrypted=encrypt_key("sk-test-key"),
        )
    )
    db.commit()


def test_openai_engine_selected(db):
    add_hotel(db, "hotel-a", AIEngineType.openai)
    engine = get_engine("hotel-a", db)
    assert isinstance(engine, OpenAIAdapter)
    assert engine.provider_name == "openai"


def test_claude_engine_selected(db):
    add_hotel(db, "hotel-b", AIEngineType.claude)
    engine = get_engine("hotel-b", db)
    assert isinstance(engine, ClaudeAdapter)
    assert engine.provider_name == "claude"


def test_unknown_hotel_raises(db):
    with pytest.raises(UnknownHotelError):
        get_engine("no-such-hotel", db)


def test_engine_swap_via_settings(db):
    """Flipping ai_engine in the settings row changes the adapter — no code change."""
    add_hotel(db, "hotel-c", AIEngineType.openai)
    assert isinstance(get_engine("hotel-c", db), OpenAIAdapter)

    row = db.query(HotelSettings).filter_by(hotel_id="hotel-c").one()
    row.ai_engine = AIEngineType.claude
    db.commit()
    assert isinstance(get_engine("hotel-c", db), ClaudeAdapter)
