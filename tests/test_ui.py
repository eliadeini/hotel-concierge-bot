from app.models.conversation_log import ConversationLog
from app.models.hotel_region_tag import HotelRegionTag
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.security.crypto import encrypt_key
from app.ui import routes as ui_routes
from tests.conftest import FakeEngine


def add_hotel(db, hotel_id, tags=()):
    hotel = HotelSettings(
        hotel_id=hotel_id, ai_engine=AIEngineType.openai, api_key_encrypted=encrypt_key("k")
    )
    db.add(hotel)
    db.commit()
    for tag in tags:
        db.add(HotelRegionTag(hotel_settings_id=hotel.id, tag=tag))
    db.commit()
    return hotel


def patch_fake_engine(monkeypatch, found_in_kb=True):
    fake_engine = FakeEngine(found_in_kb=found_in_kb)
    monkeypatch.setattr(ui_routes.engine_factory, "get_engine", lambda hotel_id, db: fake_engine)
    return fake_engine


def test_demo_page_serves_html(client):
    response = client.get("/demo")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Hotel Demo" in response.text


def test_demo_ask_happy_path(client, db, monkeypatch):
    add_hotel(db, ui_routes.DEMO_HOTEL_ID, tags=["nahariya"])
    fake_engine = patch_fake_engine(monkeypatch, found_in_kb=True)

    response = client.post("/demo/ask", json={"question": "Where should I eat?"})

    assert response.status_code == 200
    assert response.json() == {"text": "echo: Where should I eat?", "found_in_kb": True}
    assert len(fake_engine.calls) == 1
    # Merged multi-tag context, same as the real WhatsApp path — proves
    # gather_context() is actually being used, not a separate/simpler lookup.
    assert "## Region: nahariya" in fake_engine.calls[0]["context"]


def test_demo_ask_logs_conversation(client, db, monkeypatch):
    add_hotel(db, ui_routes.DEMO_HOTEL_ID, tags=["nahariya"])
    patch_fake_engine(monkeypatch, found_in_kb=False)

    client.post("/demo/ask", json={"question": "hi"})

    logs = db.query(ConversationLog).all()
    assert len(logs) == 1
    assert logs[0].hotel_id == ui_routes.DEMO_HOTEL_ID
    assert logs[0].question == "hi"
    assert logs[0].found_in_kb is False
    assert logs[0].ai_engine == "fake"


def test_demo_ask_never_leaks_raw_provider_response(client, db, monkeypatch):
    add_hotel(db, ui_routes.DEMO_HOTEL_ID, tags=["nahariya"])
    patch_fake_engine(monkeypatch)

    response = client.post("/demo/ask", json={"question": "hi"})

    assert "raw_provider_response" not in response.json()
    assert "must-never-leak" not in response.text


def test_demo_ask_hotel_not_seeded_returns_503(client):
    # No add_hotel() call — DEMO_HOTEL_ID doesn't exist in the (empty) test DB.
    response = client.post("/demo/ask", json={"question": "hi"})
    assert response.status_code == 503