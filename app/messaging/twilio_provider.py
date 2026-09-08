import httpx

from app.messaging.base import MessagingProvider

_SEND_TIMEOUT_SECONDS = 10.0


class TwilioMessagingProvider(MessagingProvider):
    provider_name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, whatsapp_number: str):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = whatsapp_number

    async def send_message(self, to: str, text: str) -> bool:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/Messages.json"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    data={"From": self._from_number, "To": f"whatsapp:{to}", "Body": text},
                    auth=(self._account_sid, self._auth_token),
                    timeout=_SEND_TIMEOUT_SECONDS,
                )
            except httpx.HTTPError:
                return False
        return response.status_code < 300
