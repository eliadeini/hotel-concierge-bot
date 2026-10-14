from app.engines import factory
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.security.crypto import decrypt_key

HEADERS = {"X-Admin-Token": "test-admin-token"}


def test_create_hotel(client, db):
    response = client.post(
        "/admin/hotels",
        json={"hotel_id": "new-hotel", "ai_engine": "openai", "api_key": "sk-raw"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {
        "hotel_id": "new-hotel",
        "ai_engine": "openai",
        "is_test": False,
        "hotel_skill_path": None,
    }
    # Key is stored encrypted, never echoed
    assert "sk-raw" not in response.text
    row = db.query(HotelSettings).filter_by(hotel_id="new-hotel").one()
    assert row.api_key_encrypted != "sk-raw"
    assert decrypt_key(row.api_key_encrypted) == "sk-raw"


def test_update_switches_engine(client, db):
    client.post(
        "/admin/hotels",
        json={"hotel_id": "h", "ai_engine": "openai", "api_key": "k1"},
        headers=HEADERS,
    )
    client.post(
        "/admin/hotels",
        json={"hotel_id": "h", "ai_engine": "claude", "api_key": "k2", "is_test": True},
        headers=HEADERS,
    )
    rows = db.query(HotelSettings).filter_by(hotel_id="h").all()
    assert len(rows) == 1
    assert rows[0].ai_engine == AIEngineType.claude
    assert rows[0].is_test is True
    assert decrypt_key(rows[0].api_key_encrypted) == "k2"


def test_wrong_token_rejected(client):
    response = client.post(
        "/admin/hotels",
        json={"hotel_id": "h", "ai_engine": "openai", "api_key": "k"},
        headers={"X-Admin-Token": "wrong"},
    )
    assert response.status_code == 401


def test_missing_token_rejected(client):
    response = client.post(
        "/admin/hotels",
        json={"hotel_id": "h", "ai_engine": "openai", "api_key": "k"},
    )
    assert response.status_code == 401


def test_create_hotel_without_api_key_stores_no_key(client, db):
    response = client.post(
        "/admin/hotels",
        json={"hotel_id": "no-key-hotel", "ai_engine": "openai"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    row = db.query(HotelSettings).filter_by(hotel_id="no-key-hotel").one()
    assert row.api_key_encrypted is None


def test_get_engine_falls_back_to_default_hotel_key_when_hotel_has_none(client, db):
    client.post(
        "/admin/hotels",
        json={
            "hotel_id": factory.DEFAULT_API_KEY_HOTEL_ID,
            "ai_engine": "openai",
            "api_key": "default-key",
        },
        headers=HEADERS,
    )
    client.post(
        "/admin/hotels",
        json={"hotel_id": "no-key-hotel", "ai_engine": "openai"},
        headers=HEADERS,
    )

    engine = factory.get_engine("no-key-hotel", db)

    assert engine._client.api_key == "default-key"


def test_get_engine_uses_own_key_over_default(client, db):
    client.post(
        "/admin/hotels",
        json={
            "hotel_id": factory.DEFAULT_API_KEY_HOTEL_ID,
            "ai_engine": "openai",
            "api_key": "default-key",
        },
        headers=HEADERS,
    )
    client.post(
        "/admin/hotels",
        json={"hotel_id": "own-key-hotel", "ai_engine": "openai", "api_key": "own-key"},
        headers=HEADERS,
    )

    engine = factory.get_engine("own-key-hotel", db)

    assert engine._client.api_key == "own-key"
