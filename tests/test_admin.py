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
