from sqlalchemy.orm import Session

from app.config import settings
from app.messaging.base import MessagingProvider, RateLimitedMessagingProvider, RateLimiter
from app.messaging.meta_direct_provider import MetaDirectMessagingProvider
from app.messaging.mock_provider import MockMessagingProvider
from app.messaging.twilio_provider import TwilioMessagingProvider
from app.models.hotel_messaging_settings import MessagingProviderType
from app.models.hotel_settings import HotelSettings
from app.security.crypto import decrypt_key


class UnknownHotelError(LookupError):
    pass


def get_messaging_provider(hotel_id: str, db: Session) -> MessagingProvider:
    """Return the configured WhatsApp provider for a hotel, wrapped with
    rate limiting.

    Resolution order: MESSAGING_PROVIDER=mock overrides everything (local
    dev, ignores hotel config); otherwise each field is taken from the
    hotel's HotelMessagingSettings row if set there, else from the global
    defaults in app/config.py.
    """
    if settings.messaging_provider == "mock":
        return MockMessagingProvider()

    hotel = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
    if hotel is None:
        raise UnknownHotelError(hotel_id)

    msg = hotel.messaging  # HotelMessagingSettings | None

    # If hotel doesn't have different settings, take the default settings
    provider_type = (
        msg.provider if msg and msg.provider else MessagingProviderType(settings.messaging_provider)
    )

    provider: MessagingProvider
    if provider_type == MessagingProviderType.meta_direct:
        phone_number_id = (
            msg.meta_phone_number_id if msg and msg.meta_phone_number_id else settings.meta_phone_number_id
        )
        access_token = (
            decrypt_key(msg.meta_access_token_encrypted)
            if msg and msg.meta_access_token_encrypted
            else settings.meta_access_token
        )
        provider = MetaDirectMessagingProvider(phone_number_id, access_token)
    else:
        account_sid = (
            msg.twilio_account_sid if msg and msg.twilio_account_sid else settings.twilio_account_sid
        )
        auth_token = (
            decrypt_key(msg.twilio_auth_token_encrypted)
            if msg and msg.twilio_auth_token_encrypted
            else settings.twilio_auth_token
        )
        whatsapp_number = (
            msg.twilio_whatsapp_number
            if msg and msg.twilio_whatsapp_number
            else settings.twilio_whatsapp_number
        )
        provider = TwilioMessagingProvider(account_sid, auth_token, whatsapp_number)

    per_hotel_limit = (
        msg.daily_message_limit_override
        if msg and msg.daily_message_limit_override is not None
        else settings.whatsapp_daily_limit_per_hotel
    )
    rate_limiter = RateLimiter(
        db,
        per_phone_limit=settings.whatsapp_daily_limit_per_phone,
        per_hotel_limit=per_hotel_limit,
        global_limit=settings.whatsapp_daily_limit_global,
    )
    return RateLimitedMessagingProvider(provider, rate_limiter, hotel_id)