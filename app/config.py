import enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class UIMode(str, enum.Enum):
    website = "website"
    hotel = "hotel"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Master key for encrypting hotel API keys at rest. Loaded from the
    # environment only — never hardcoded, never stored in the DB.
    master_encryption_key: str = ""

    database_url: str = "sqlite:///./data/app.db"

    # "app" logger level (see app/main.py). Set to DEBUG to log the full
    # system_prompt/context/question sent to the AI engine on every
    # request — see app/api/chat.py::answer_question. Off (INFO) by
    # default; never shown in any API response, logs only.
    log_level: str = "INFO"

    # Shared secret guarding /admin/hotels. Empty means the endpoint is disabled.
    admin_token: str = ""

    # Which template GET / serves (see app/ui/routes.py): "website" is the
    # general public site (app/ui/templates/website.html); "hotel" serves
    # the same WhatsApp-lookalike look used for hotel demos. GET /demo
    # always serves the hotel look regardless of this setting, so it stays
    # available for demoing to prospective hotel clients either way.
    ui_mode: UIMode = UIMode.website

    openai_model: str = "gpt-5.6-luna"
    claude_model: str = "claude-haiku-4-5-20251001"

    # Global WhatsApp messaging defaults — used when a hotel has no
    # HotelMessagingSettings override. "mock" logs instead of sending, for
    # local dev.
    messaging_provider: str = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""
    meta_phone_number_id: str = ""
    meta_access_token: str = ""
    # Signs inbound Meta webhook payloads (X-Hub-Signature-256) — the App
    # Secret from App Dashboard > App Settings > Basic, NOT the access token.
    meta_app_secret: str = ""

    # Verifies inbound webhook setup calls (Meta-style hub.verify_token handshake).
    whatsapp_webhook_verify_token: str = ""

    # Daily send caps, to avoid an unexpectedly large WhatsApp bill.
    whatsapp_daily_limit_per_phone: int = 50
    whatsapp_daily_limit_per_hotel: int = 200
    whatsapp_daily_limit_global: int = 500


settings = Settings()
