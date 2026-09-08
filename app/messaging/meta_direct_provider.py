import httpx

from app.messaging.base import MessagingProvider

_SEND_TIMEOUT_SECONDS = 10.0
_GRAPH_API_VERSION = "v20.0"


class MetaDirectMessagingProvider(MessagingProvider):
    """Sends via the WhatsApp Cloud API directly (Meta Graph API).

    Untested against a live Meta Business account — mirrors
    TwilioMessagingProvider's shape, but treat this as a stub until it's
    been exercised for real.
    """

    provider_name = "meta_direct"

    def __init__(self, phone_number_id: str, access_token: str):
        self._phone_number_id = phone_number_id
        self._access_token = access_token

    async def send_message(self, to: str, text: str) -> bool:
        url = f"https://graph.facebook.com/{_GRAPH_API_VERSION}/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=_SEND_TIMEOUT_SECONDS,
                )
            except httpx.HTTPError:
                return False
        return response.status_code < 300