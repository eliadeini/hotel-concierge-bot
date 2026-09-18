from app.messaging import inbound
from app.models.hotel_region_tag import HotelRegionTag
from app.models.hotel_settings import AIEngineType, HotelSettings, PresentationMode
from app.security.crypto import encrypt_key
from tests.conftest import FakeKnowledgeSource


def add_hotel(db, hotel_id, presentation_mode=PresentationMode.hotel, tags=("nahariya",)):
    hotel = HotelSettings(
        hotel_id=hotel_id,
        ai_engine=AIEngineType.openai,
        api_key_encrypted=encrypt_key("k"),
        presentation_mode=presentation_mode,
    )
    db.add(hotel)
    db.commit()
    for tag in tags:
        db.add(HotelRegionTag(hotel_settings_id=hotel.id, tag=tag))
    db.commit()
    return hotel


def test_neutralize_landmarks_strips_h34_variants():
    text = "מסעדה כ-2 דקות הליכה ממלון H34 וגם ליד H34 עצמו."
    result = inbound._neutralize_landmarks(text)
    assert "H34" not in result
    assert "מלון H34" not in result


def test_gather_context_neutralizes_for_website_mode(db, monkeypatch):
    hotel = add_hotel(db, "test-website-hotel", presentation_mode=PresentationMode.website)
    monkeypatch.setattr(
        inbound, "_markdown_source", FakeKnowledgeSource(context="כ-2 דקות הליכה ממלון H34")
    )

    _, context = inbound.gather_context(hotel)

    assert "H34" not in context


def test_gather_context_leaves_hotel_mode_untouched(db, monkeypatch):
    hotel = add_hotel(db, "test-hotel-hotel", presentation_mode=PresentationMode.hotel)
    monkeypatch.setattr(
        inbound, "_markdown_source", FakeKnowledgeSource(context="כ-2 דקות הליכה ממלון H34")
    )

    _, context = inbound.gather_context(hotel)

    assert "ממלון H34" in context


def test_gather_context_leaves_hotel_demo_mode_untouched(db, monkeypatch):
    hotel = add_hotel(db, "test-hotel-demo-hotel", presentation_mode=PresentationMode.hotel_demo)
    monkeypatch.setattr(
        inbound, "_markdown_source", FakeKnowledgeSource(context="כ-2 דקות הליכה ממלון H34")
    )

    _, context = inbound.gather_context(hotel)

    assert "ממלון H34" in context