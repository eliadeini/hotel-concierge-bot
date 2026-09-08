from datetime import date

from app.api.chat import get_messaging_provider_factory
from app.main import app
from app.models.guest_session import GuestFlowState, GuestSession
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.security.crypto import encrypt_key
from tests.conftest import FakeMessagingProvider

HEADERS = {"X-Admin-Token": "test-admin-token"}


def add_hotel(db, hotel_id="hotel-a"):
    hotel = HotelSettings(
        hotel_id=hotel_id, ai_engine=AIEngineType.openai, api_key_encrypted=encrypt_key("k")
    )
    db.add(hotel)
    db.commit()
    return hotel


def override_messaging(sends_ok: bool = True) -> FakeMessagingProvider:
    fake_provider = FakeMessagingProvider()
    if not sends_ok:

        async def fail(to, text):
            return False

        fake_provider.send_message = fail  # type: ignore[method-assign]

    app.dependency_overrides[get_messaging_provider_factory] = lambda: (
        lambda hotel_id, db: fake_provider
    )
    return fake_provider


def test_checkin_sends_welcome_and_starts_flow(client, db):
    add_hotel(db)
    fake_provider = override_messaging()

    response = client.post(
        "/admin/hotels/hotel-a/guests",
        json={"phone": "+972500000001", "check_in": "2026-08-10", "check_out": "2026-08-15"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["welcome_sent"] is True
    assert body["phone"] == "+972500000001"
    assert body["check_in"] == "2026-08-10"
    assert body["check_out"] == "2026-08-15"

    row = db.query(GuestSession).filter_by(phone="+972500000001").one()
    assert row.welcome_sent_at is not None
    assert row.flow_state == GuestFlowState.awaiting_help_confirmation
    assert len(fake_provider.sent) == 1
    assert fake_provider.sent[0][0] == "+972500000001"


def test_checkin_defaults_check_in_to_today(client, db):
    add_hotel(db)
    override_messaging()

    response = client.post(
        "/admin/hotels/hotel-a/guests", json={"phone": "+972500000002"}, headers=HEADERS
    )

    assert response.status_code == 200
    assert response.json()["check_in"] == date.today().isoformat()
    assert response.json()["check_out"] is None


def test_checkin_failed_send_does_not_start_flow(client, db):
    add_hotel(db)
    override_messaging(sends_ok=False)

    response = client.post(
        "/admin/hotels/hotel-a/guests", json={"phone": "+972500000003"}, headers=HEADERS
    )

    assert response.status_code == 200
    assert response.json()["welcome_sent"] is False
    row = db.query(GuestSession).filter_by(phone="+972500000003").one()
    assert row.welcome_sent_at is None
    assert row.flow_state is None


def test_checkin_unknown_hotel_returns_404(client, db):
    override_messaging()
    response = client.post(
        "/admin/hotels/no-such-hotel/guests", json={"phone": "+972500000004"}, headers=HEADERS
    )
    assert response.status_code == 404


def test_checkin_missing_token_rejected(client, db):
    add_hotel(db)
    response = client.post("/admin/hotels/hotel-a/guests", json={"phone": "+972500000005"})
    assert response.status_code == 401


def test_checkin_wrong_token_rejected(client, db):
    add_hotel(db)
    response = client.post(
        "/admin/hotels/hotel-a/guests",
        json={"phone": "+972500000006"},
        headers={"X-Admin-Token": "wrong"},
    )
    assert response.status_code == 401


def test_recheckin_updates_same_row_and_resets_stale_state(client, db):
    add_hotel(db)
    override_messaging()

    client.post(
        "/admin/hotels/hotel-a/guests",
        json={"phone": "+972500000007", "check_in": "2026-08-01", "check_out": "2026-08-05"},
        headers=HEADERS,
    )
    # Simulate a stale in-progress flow left over from the previous stay.
    row = db.query(GuestSession).filter_by(phone="+972500000007").one()
    row.flow_state = GuestFlowState.awaiting_trip_type
    db.commit()

    client.post(
        "/admin/hotels/hotel-a/guests",
        json={"phone": "+972500000007", "check_in": "2026-09-01", "check_out": "2026-09-05"},
        headers=HEADERS,
    )

    # The endpoint updates via its own DB session (Depends(get_db)); this
    # test's `db` fixture session has the pre-update row cached in its
    # identity map, so it needs to expire before re-querying.
    db.expire_all()
    rows = db.query(GuestSession).filter_by(phone="+972500000007").all()
    assert len(rows) == 1  # updated in place, not duplicated
    assert rows[0].check_in == date(2026, 9, 1)
    # Reset by the upsert, then re-set to the flow's first step by the new send.
    assert rows[0].flow_state == GuestFlowState.awaiting_help_confirmation
