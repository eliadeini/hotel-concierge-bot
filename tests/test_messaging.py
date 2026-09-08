import asyncio

import httpx
import pytest

from app.messaging import factory as messaging_factory
from app.messaging.base import RateLimitedMessagingProvider, RateLimiter
from app.messaging.meta_direct_provider import MetaDirectMessagingProvider
from app.messaging.mock_provider import MockMessagingProvider
from app.messaging.twilio_provider import TwilioMessagingProvider
from app.models.hotel_messaging_settings import HotelMessagingSettings
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.models.message_rate_limit import MessageRateLimitCounter, RateLimitScope
from app.security.crypto import encrypt_key
from tests.conftest import FakeMessagingProvider


def _run(coro):
    return asyncio.run(coro)


def add_hotel(db, hotel_id):
    hotel = HotelSettings(
        hotel_id=hotel_id, ai_engine=AIEngineType.openai, api_key_encrypted=encrypt_key("k")
    )
    db.add(hotel)
    db.commit()
    return hotel


# --- RateLimiter -------------------------------------------------------


def test_rate_limiter_blocks_per_phone_limit(db):
    limiter = RateLimiter(db, per_phone_limit=2, per_hotel_limit=100, global_limit=100)
    assert limiter.check_and_increment(hotel_id="h1", phone="+972500000000") is True
    assert limiter.check_and_increment(hotel_id="h1", phone="+972500000000") is True
    assert limiter.check_and_increment(hotel_id="h1", phone="+972500000000") is False


def test_rate_limiter_blocks_per_hotel_limit_across_different_phones(db):
    limiter = RateLimiter(db, per_phone_limit=100, per_hotel_limit=2, global_limit=100)
    assert limiter.check_and_increment(hotel_id="h1", phone="+9721") is True
    assert limiter.check_and_increment(hotel_id="h1", phone="+9722") is True
    assert limiter.check_and_increment(hotel_id="h1", phone="+9723") is False


def test_rate_limiter_blocks_global_limit_across_different_hotels(db):
    limiter = RateLimiter(db, per_phone_limit=100, per_hotel_limit=100, global_limit=2)
    assert limiter.check_and_increment(hotel_id="h1", phone="+9721") is True
    assert limiter.check_and_increment(hotel_id="h2", phone="+9722") is True
    assert limiter.check_and_increment(hotel_id="h3", phone="+9723") is False


def test_rate_limiter_blocked_attempt_does_not_increment_counter(db):
    limiter = RateLimiter(db, per_phone_limit=1, per_hotel_limit=100, global_limit=100)
    limiter.check_and_increment(hotel_id="h1", phone="+9721")
    limiter.check_and_increment(hotel_id="h1", phone="+9721")  # blocked
    row = (
        db.query(MessageRateLimitCounter)
        .filter_by(scope=RateLimitScope.phone, scope_key="+9721")
        .one()
    )
    assert row.count == 1


# --- RateLimitedMessagingProvider ---------------------------------------


def test_rate_limited_provider_blocks_send_after_limit(db):
    wrapped = FakeMessagingProvider()
    limiter = RateLimiter(db, per_phone_limit=1, per_hotel_limit=100, global_limit=100)
    provider = RateLimitedMessagingProvider(wrapped, limiter, hotel_id="h1")

    assert _run(provider.send_message("+9721", "hi")) is True
    assert _run(provider.send_message("+9721", "hi again")) is False
    assert wrapped.sent == [("+9721", "hi")]  # second call never reached the wrapped provider


def test_rate_limited_provider_exposes_wrapped_provider_name(db):
    wrapped = FakeMessagingProvider()
    limiter = RateLimiter(db, per_phone_limit=100, per_hotel_limit=100, global_limit=100)
    provider = RateLimitedMessagingProvider(wrapped, limiter, hotel_id="h1")
    assert provider.provider_name == "fake"


# --- MockMessagingProvider ------------------------------------------------


def test_mock_provider_always_succeeds():
    assert _run(MockMessagingProvider().send_message("+9721", "hello")) is True


# --- TwilioMessagingProvider (network mocked) ---------------------------


def test_twilio_provider_sends_expected_request(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 201

    async def fake_post(self, url, *, data=None, auth=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        captured["auth"] = auth
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    provider = TwilioMessagingProvider("SIDXXX", "tokenXXX", "whatsapp:+14155238886")
    result = _run(provider.send_message("+972500000000", "hello guest"))

    assert result is True
    assert captured["url"] == "https://api.twilio.com/2010-04-01/Accounts/SIDXXX/Messages.json"
    assert captured["data"] == {
        "From": "whatsapp:+14155238886",
        "To": "whatsapp:+972500000000",
        "Body": "hello guest",
    }
    assert captured["auth"] == ("SIDXXX", "tokenXXX")


def test_twilio_provider_returns_false_on_http_error(monkeypatch):
    async def fake_post(self, *args, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    provider = TwilioMessagingProvider("SID", "token", "whatsapp:+1")
    assert _run(provider.send_message("+972500000000", "hi")) is False


def test_twilio_provider_returns_false_on_error_status(monkeypatch):
    class FakeResponse:
        status_code = 400

    async def fake_post(self, *args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    provider = TwilioMessagingProvider("SID", "token", "whatsapp:+1")
    assert _run(provider.send_message("+972500000000", "hi")) is False


# --- MetaDirectMessagingProvider (network mocked) ------------------------


def test_meta_direct_provider_sends_expected_request(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

    async def fake_post(self, url, *, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    provider = MetaDirectMessagingProvider("PHONE_ID", "META_TOKEN")
    result = _run(provider.send_message("+972500000000", "hi"))

    assert result is True
    assert "PHONE_ID" in captured["url"]
    assert captured["headers"] == {"Authorization": "Bearer META_TOKEN"}
    assert captured["json"]["to"] == "+972500000000"
    assert captured["json"]["text"]["body"] == "hi"


# --- factory.get_messaging_provider ---------------------------------------


def test_factory_hotel_specific_credentials_override_global(db, monkeypatch):
    monkeypatch.setattr(messaging_factory.settings, "messaging_provider", "twilio")
    monkeypatch.setattr(messaging_factory.settings, "twilio_account_sid", "GLOBAL_SID")
    monkeypatch.setattr(messaging_factory.settings, "twilio_auth_token", "GLOBAL_TOKEN")
    monkeypatch.setattr(messaging_factory.settings, "twilio_whatsapp_number", "whatsapp:+1global")

    hotel = add_hotel(db, "h1")
    db.add(
        HotelMessagingSettings(
            hotel_settings_id=hotel.id,
            twilio_account_sid="HOTEL_SID",
            twilio_auth_token_encrypted=encrypt_key("HOTEL_TOKEN"),
            twilio_whatsapp_number="whatsapp:+1hotel",
        )
    )
    db.commit()

    provider = messaging_factory.get_messaging_provider("h1", db)
    assert isinstance(provider, RateLimitedMessagingProvider)
    inner = provider._wrapped
    assert isinstance(inner, TwilioMessagingProvider)
    assert inner._account_sid == "HOTEL_SID"
    assert inner._auth_token == "HOTEL_TOKEN"
    assert inner._from_number == "whatsapp:+1hotel"


def test_factory_falls_back_to_global_when_no_hotel_override(db, monkeypatch):
    monkeypatch.setattr(messaging_factory.settings, "messaging_provider", "twilio")
    monkeypatch.setattr(messaging_factory.settings, "twilio_account_sid", "GLOBAL_SID")
    monkeypatch.setattr(messaging_factory.settings, "twilio_auth_token", "GLOBAL_TOKEN")
    monkeypatch.setattr(messaging_factory.settings, "twilio_whatsapp_number", "whatsapp:+1global")

    add_hotel(db, "h2")

    provider = messaging_factory.get_messaging_provider("h2", db)
    assert provider._wrapped._account_sid == "GLOBAL_SID"


def test_factory_per_hotel_rate_limit_override(db, monkeypatch):
    class FakeResponse:
        status_code = 201

    async def fake_post(self, *args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(messaging_factory.settings, "messaging_provider", "twilio")
    monkeypatch.setattr(messaging_factory.settings, "whatsapp_daily_limit_per_hotel", 200)

    hotel = add_hotel(db, "h3")
    db.add(HotelMessagingSettings(hotel_settings_id=hotel.id, daily_message_limit_override=1))
    db.commit()

    provider = messaging_factory.get_messaging_provider("h3", db)
    assert _run(provider.send_message("+9721", "one")) is True
    assert _run(provider.send_message("+9722", "two")) is False  # hotel cap of 1 hit


def test_factory_mock_override_ignores_hotel_config(db, monkeypatch):
    monkeypatch.setattr(messaging_factory.settings, "messaging_provider", "mock")
    provider = messaging_factory.get_messaging_provider("nonexistent-hotel", db)
    assert isinstance(provider, MockMessagingProvider)


def test_factory_unknown_hotel_raises(db, monkeypatch):
    monkeypatch.setattr(messaging_factory.settings, "messaging_provider", "twilio")
    with pytest.raises(messaging_factory.UnknownHotelError):
        messaging_factory.get_messaging_provider("nope", db)
