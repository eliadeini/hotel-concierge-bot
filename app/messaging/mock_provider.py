import logging

from app.messaging.base import MessagingProvider

logger = logging.getLogger(__name__)


class MockMessagingProvider(MessagingProvider):
    """Logs outbound messages instead of sending them. For local dev only —
    selected globally via MESSAGING_PROVIDER=mock (see app/messaging/factory.py).
    """

    provider_name = "mock"

    async def send_message(self, to: str, text: str) -> bool:
        logger.info("[mock-whatsapp] to=%s text=%r", to, text)
        return True
