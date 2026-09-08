import os

from cryptography.fernet import Fernet

# Must be set BEFORE any app import — app.config.settings is created at import time.
os.environ["MASTER_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory
os.environ["ADMIN_TOKEN"] = "test-admin-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.engines.base import AIEngine, EngineResponse  # noqa: E402
from app.knowledge.base import KnowledgeSource  # noqa: E402
from app.main import app  # noqa: E402
from app.messaging.base import MessagingProvider  # noqa: E402


class FakeEngine(AIEngine):
    """In-memory engine — no API keys, no network."""

    provider_name = "fake"

    def __init__(self, found_in_kb: bool = True):
        self._found_in_kb = found_in_kb
        self.calls: list[dict] = []

    def ask(self, system_prompt: str, context: str, question: str) -> EngineResponse:
        self.calls.append(
            {"system_prompt": system_prompt, "context": context, "question": question}
        )
        return EngineResponse(
            text=f"echo: {question}",
            found_in_kb=self._found_in_kb,
            raw_provider_response={"debug": "must-never-leak"},
        )


class FakeKnowledgeSource(KnowledgeSource):
    """Returns a fixed in-memory string — no disk access."""

    def __init__(self, context: str = "fake knowledge context"):
        self._context = context

    def get_context(self, hotel_id, region, category=None) -> str:
        return self._context


class FakeMessagingProvider(MessagingProvider):
    """In-memory provider — no network, no rate limiting."""

    provider_name = "fake"

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def send_message(self, to: str, text: str) -> bool:
        self.sent.append((to, text))
        return True


@pytest.fixture(autouse=True)
def fresh_db():
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
