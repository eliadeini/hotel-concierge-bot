from datetime import date

from twilio.request_validator import RequestValidator

from app.api import meta_whatsapp_webhook, twilio_whatsapp_webhook
from app.messaging import inbound
from app.messaging.flow import DECLINE_ACK, TRIP_TYPE_ACK, TRIP_TYPE_QUESTION
from app.models.conversation_log import ConversationLog
from app.models.guest_session import GuestFlowState, GuestSession, TripType
from app.models.hotel_messaging_settings import HotelMessagingSettings
from app.models.hotel_region_tag import HotelRegionTag
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.security.crypto import encrypt_key
from tests.conftest import FakeEngine, FakeMessagingProvider

META_WEBHOOK_URL = "http://testserver/webhook/whatsapp"
TWILIO_WEBHOOK_URL = "http://testserver/webhook/whatsapp/twilio"


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


def sign(auth_token: str, params: dict) -> str:
    return RequestValidator(auth_token).compute_signature(TWILIO_WEBHOOK_URL, params)


def add_guest(db, hotel, phone, flow_state=None, trip_type=None):
    guest = GuestSession(
        hotel_settings_id=hotel.id,
        phone=phone,
        check_in=date.today(),
        flow_state=flow_state,
        trip_type=trip_type,
    )
    db.add(guest)
    db.commit()
    return guest


def patch_fakes(monkeypatch):
    """Swap the engine/messaging factories for in-memory fakes so no real
    API keys, network calls, or provider SDKs are touched. Both webhook
    handlers funnel into app.messaging.inbound's processing, so patching
    there covers Meta and Twilio requests alike."""
    fake_engine = FakeEngine(found_in_kb=True)
    fake_provider = FakeMessagingProvider()
    monkeypatch.setattr(inbound.engine_factory, "get_engine", lambda hotel_id, db: fake_engine)
    monkeypatch.setattr(
        inbound.messaging_factory, "get_messaging_provider", lambda hotel_id, db: fake_provider
    )
    return fake_engine, fake_provider


# --- GET verification (Meta) ------------------------------------------------


def test_get_verification_success(client, monkeypatch):
    monkeypatch.setattr(meta_whatsapp_webhook.settings, "whatsapp_webhook_verify_token", "secret")
    response = client.get(
        "/webhook/whatsapp",
        params={"hub.verify_token": "secret", "hub.challenge": "echo-me"},
    )
    assert response.status_code == 200
    assert response.text == "echo-me"


def test_get_verification_wrong_token_rejected(client, monkeypatch):
    monkeypatch.setattr(meta_whatsapp_webhook.settings, "whatsapp_webhook_verify_token", "secret")
    response = client.get(
        "/webhook/whatsapp",
        params={"hub.verify_token": "wrong", "hub.challenge": "echo-me"},
    )
    assert response.status_code == 403


def test_get_verification_not_configured_rejected(client, monkeypatch):
    monkeypatch.setattr(meta_whatsapp_webhook.settings, "whatsapp_webhook_verify_token", "")
    response = client.get(
        "/webhook/whatsapp",
        params={"hub.verify_token": "anything", "hub.challenge": "echo-me"},
    )
    assert response.status_code == 403


# --- POST (Twilio): signature validation & hotel resolution ----------------


def test_post_valid_signature_single_tenant_fallback(client, db, monkeypatch):
    """No HotelMessagingSettings row: falls back to the global number, and
    works because exactly one hotel exists."""
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    add_hotel(db, "hotel-a", tags=["nahariya"])
    fake_engine, fake_provider = patch_fakes(monkeypatch)

    params = {
        "To": "whatsapp:+1000",
        "From": "whatsapp:+972500000001",
        "Body": "Where should I eat?",
    }
    response = client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    assert response.status_code == 200
    assert len(fake_engine.calls) == 1
    assert fake_engine.calls[0]["question"] == "Where should I eat?"
    assert fake_provider.sent == [("+972500000001", "echo: Where should I eat?")]


def test_post_invalid_signature_rejected(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    add_hotel(db, "hotel-a")
    fake_engine, fake_provider = patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+9725", "Body": "hi"}
    response = client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": "not-a-real-signature"},
    )

    assert response.status_code == 403
    assert fake_engine.calls == []
    assert fake_provider.sent == []


def test_post_unknown_number_rejected(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    add_hotel(db, "hotel-a")

    params = {"To": "whatsapp:+9999999", "From": "whatsapp:+9725", "Body": "hi"}
    response = client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )
    assert response.status_code == 404


def test_post_ambiguous_fallback_rejected_with_multiple_hotels(client, db, monkeypatch):
    """Global number, no hotel-specific override, and more than one hotel
    exists — can't attribute the message, so it's rejected rather than
    guessing."""
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    add_hotel(db, "hotel-a")
    add_hotel(db, "hotel-b")

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+9725", "Body": "hi"}
    response = client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )
    assert response.status_code == 404


def test_post_hotel_specific_number_and_token(client, db, monkeypatch):
    """A hotel with its own number/token is matched and validated with its
    own (decrypted) auth token, independent of the global default."""
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    hotel = add_hotel(db, "hotel-specific")
    db.add(
        HotelMessagingSettings(
            hotel_settings_id=hotel.id,
            twilio_whatsapp_number="whatsapp:+2000",
            twilio_auth_token_encrypted=encrypt_key("hotel-token"),
        )
    )
    db.commit()
    fake_engine, fake_provider = patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+2000", "From": "whatsapp:+9725", "Body": "hi"}
    response = client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("hotel-token", params)},
    )

    assert response.status_code == 200
    assert len(fake_engine.calls) == 1


def test_post_merges_context_across_all_region_tags(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    add_hotel(db, "hotel-a", tags=["nahariya", "made-up-tag-with-no-content"])
    fake_engine, _ = patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+9725", "Body": "hi"}
    client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    assert len(fake_engine.calls) == 1
    # nahariya has real knowledge-base content; the made-up tag contributes
    # nothing but shouldn't break the merge.
    assert "## Region: nahariya" in fake_engine.calls[0]["context"]


def test_post_logs_conversation_anonymously(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    add_hotel(db, "hotel-a", tags=["nahariya"])
    patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+972500000009", "Body": "hi there"}
    client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    logs = db.query(ConversationLog).all()
    assert len(logs) == 1
    assert logs[0].question == "hi there"
    assert "+972500000009" not in logs[0].region  # no phone number leaks into the log


# --- Onboarding flow (via Twilio) ------------------------------------------


def test_post_flow_yes_moves_to_trip_type_question(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    hotel = add_hotel(db, "hotel-a")
    add_guest(db, hotel, "+972500000010", flow_state=GuestFlowState.awaiting_help_confirmation)
    fake_engine, fake_provider = patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+972500000010", "Body": "כן"}
    response = client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    assert response.status_code == 200
    assert fake_engine.calls == []  # AI engine never touched
    assert fake_provider.sent == [("+972500000010", TRIP_TYPE_QUESTION)]
    guest = db.query(GuestSession).filter_by(phone="+972500000010").one()
    assert guest.flow_state == GuestFlowState.awaiting_trip_type


def test_post_flow_no_ends_with_decline_ack(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    hotel = add_hotel(db, "hotel-a")
    add_guest(db, hotel, "+972500000011", flow_state=GuestFlowState.awaiting_help_confirmation)
    fake_engine, fake_provider = patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+972500000011", "Body": "לא תודה"}
    client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    assert fake_engine.calls == []
    assert fake_provider.sent == [("+972500000011", DECLINE_ACK)]
    guest = db.query(GuestSession).filter_by(phone="+972500000011").one()
    assert guest.flow_state is None


def test_post_flow_unrecognized_reply_reprompts(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    hotel = add_hotel(db, "hotel-a")
    add_guest(db, hotel, "+972500000012", flow_state=GuestFlowState.awaiting_help_confirmation)
    fake_engine, fake_provider = patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+972500000012", "Body": "מה?"}
    client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    assert fake_engine.calls == []
    assert fake_provider.sent[0][1] == "לא הבנתי, אפשר לענות כן או לא?"
    guest = db.query(GuestSession).filter_by(phone="+972500000012").one()
    assert guest.flow_state == GuestFlowState.awaiting_help_confirmation  # unchanged, can retry


def test_post_flow_trip_type_business_stores_answer(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    hotel = add_hotel(db, "hotel-a")
    add_guest(db, hotel, "+972500000013", flow_state=GuestFlowState.awaiting_trip_type)
    fake_engine, fake_provider = patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+972500000013", "Body": "נסיעה עסקית"}
    client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    assert fake_engine.calls == []
    assert fake_provider.sent == [("+972500000013", TRIP_TYPE_ACK)]
    guest = db.query(GuestSession).filter_by(phone="+972500000013").one()
    assert guest.flow_state is None
    assert guest.trip_type == TripType.business


def test_post_flow_trip_type_vacation_stores_answer(client, db, monkeypatch):
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    hotel = add_hotel(db, "hotel-a")
    add_guest(db, hotel, "+972500000014", flow_state=GuestFlowState.awaiting_trip_type)
    patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+972500000014", "Body": "חופשה"}
    client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    guest = db.query(GuestSession).filter_by(phone="+972500000014").one()
    assert guest.trip_type == TripType.vacation


def test_post_guest_with_no_active_flow_uses_ai_engine(client, db, monkeypatch):
    """A GuestSession row exists (from a prior, completed stay) but
    flow_state is None — falls straight through to normal AI chat."""
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_whatsapp_number", "whatsapp:+1000")
    monkeypatch.setattr(twilio_whatsapp_webhook.settings, "twilio_auth_token", "global-token")
    hotel = add_hotel(db, "hotel-a", tags=["nahariya"])
    add_guest(db, hotel, "+972500000015", flow_state=None)
    fake_engine, _ = patch_fakes(monkeypatch)

    params = {"To": "whatsapp:+1000", "From": "whatsapp:+972500000015", "Body": "Where to eat?"}
    client.post(
        "/webhook/whatsapp/twilio",
        data=params,
        headers={"X-Twilio-Signature": sign("global-token", params)},
    )

    assert len(fake_engine.calls) == 1
    assert fake_engine.calls[0]["question"] == "Where to eat?"