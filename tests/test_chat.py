import logging

from app.api.chat import (
    _closed_business_patterns,
    _find_closed_mention,
    get_engine_factory,
    get_knowledge_source,
)
from app.engines.base import AIEngine, EngineResponse
from app.main import app
from app.models.conversation_log import ConversationLog
from app.models.hotel_settings import AIEngineType, HotelSettings, PresentationMode
from app.security.crypto import encrypt_key
from tests.conftest import FakeEngine, FakeKnowledgeSource


def override_with_fakes(found_in_kb=True, context="fake knowledge context"):
    fake_engine = FakeEngine(found_in_kb=found_in_kb)
    app.dependency_overrides[get_knowledge_source] = lambda: FakeKnowledgeSource(context)
    app.dependency_overrides[get_engine_factory] = lambda: (
        lambda hotel_id, db: fake_engine
    )
    return fake_engine


def add_hotel(db, hotel_id, presentation_mode):
    hotel = HotelSettings(
        hotel_id=hotel_id,
        ai_engine=AIEngineType.openai,
        api_key_encrypted=encrypt_key("k"),
        presentation_mode=presentation_mode,
    )
    db.add(hotel)
    db.commit()
    return hotel


def test_chat_happy_path(client):
    override_with_fakes(found_in_kb=True)
    response = client.post(
        "/chat",
        json={"hotel_id": "h1", "region": "nahariya", "question": "Where to eat?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "echo: Where to eat?"
    assert body["found_in_kb"] is True
    assert isinstance(body["conversation_id"], int)


def test_chat_never_leaks_raw_provider_response(client):
    override_with_fakes()
    response = client.post(
        "/chat", json={"hotel_id": "h1", "region": "nahariya", "question": "hi"}
    )
    assert "raw_provider_response" not in response.json()
    assert "must-never-leak" not in response.text


def test_chat_passes_context_to_engine(client):
    fake_engine = override_with_fakes(context="THE-CONTEXT")
    client.post(
        "/chat", json={"hotel_id": "h1", "region": "nahariya", "question": "hi"}
    )
    assert len(fake_engine.calls) == 1
    assert "THE-CONTEXT" in fake_engine.calls[0]["context"]


def test_chat_website_mode_prompt_never_mentions_front_desk(client, db):
    add_hotel(db, "site-1", PresentationMode.website)
    fake_engine = override_with_fakes()
    client.post("/chat", json={"hotel_id": "site-1", "region": "nahariya", "question": "hi"})
    assert "front desk" not in fake_engine.calls[0]["system_prompt"]


def test_chat_hotel_mode_prompt_mentions_front_desk(client, db):
    add_hotel(db, "hotel-1", PresentationMode.hotel)
    fake_engine = override_with_fakes()
    client.post("/chat", json={"hotel_id": "hotel-1", "region": "nahariya", "question": "hi"})
    assert "front desk" in fake_engine.calls[0]["system_prompt"]


def test_chat_no_hotel_row_defaults_to_website_style_prompt(client):
    # No HotelSettings row at all (fake engine_factory below doesn't
    # validate hotel existence, same as test_chat_happy_path above) — must
    # default to the safer website-style prompt, never leaking "front desk"
    # when there's genuinely no known hotel to attribute it to.
    fake_engine = override_with_fakes()
    client.post(
        "/chat", json={"hotel_id": "no-such-hotel", "region": "nahariya", "question": "hi"}
    )
    assert "front desk" not in fake_engine.calls[0]["system_prompt"]


def test_chat_logs_anonymously(client, db):
    override_with_fakes(found_in_kb=False)
    client.post(
        "/chat",
        json={"hotel_id": "h1", "region": "eilat", "question": "Dolphins?"},
    )
    logs = db.query(ConversationLog).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.hotel_id == "h1"
    assert log.region == "eilat"
    assert log.question == "Dolphins?"
    assert log.answer == "echo: Dolphins?"
    assert log.found_in_kb is False
    assert log.ai_engine == "fake"


def test_chat_unknown_hotel_returns_404(client):
    # No overrides — real factory hits the (empty) DB.
    response = client.post(
        "/chat", json={"hotel_id": "ghost", "region": "nahariya", "question": "hi"}
    )
    assert response.status_code == 404


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


# --- Closed-business safety net --------------------------------------------

CLOSED_CONTEXT = (
    "### Crazy Bar\ncategory: closed | region: נהריה | updated: 2026-10-11\n"
    "נסגר לפני כ-5 שנים."
)


class _SequencedEngine(AIEngine):
    """Returns each text in `texts` in order, repeating the last one once
    exhausted — lets a test script a first draft and a corrected retry."""

    provider_name = "fake"

    def __init__(self, texts: list[str], found_in_kb: bool = False):
        self._texts = list(texts)
        self._found_in_kb = found_in_kb
        self.calls: list[dict] = []

    def ask(self, system_prompt, context, question) -> EngineResponse:
        self.calls.append(
            {"system_prompt": system_prompt, "context": context, "question": question}
        )
        text = self._texts.pop(0) if len(self._texts) > 1 else self._texts[0]
        return EngineResponse(text=text, found_in_kb=self._found_in_kb)


def override_with_engine(engine, context):
    app.dependency_overrides[get_knowledge_source] = lambda: FakeKnowledgeSource(context)
    app.dependency_overrides[get_engine_factory] = lambda: (lambda hotel_id, db: engine)


def test_chat_retries_once_when_reply_mentions_closed_business(client, db):
    engine = _SequencedEngine(["I recommend Crazy Bar for dinner.", "I recommend Ruben instead."])
    override_with_engine(engine, CLOSED_CONTEXT)
    response = client.post(
        "/chat", json={"hotel_id": "h1", "region": "nahariya", "question": "Meat restaurant?"}
    )
    assert "Crazy Bar" not in response.json()["text"]
    assert len(engine.calls) == 2
    log = db.query(ConversationLog).one()
    assert log.answer == response.json()["text"]


def test_chat_redacts_when_closed_business_survives_retry(client, caplog):
    engine = _SequencedEngine(
        ["Try Crazy Bar.", "Crazy Bar is still a solid pick."]
    )
    override_with_engine(engine, CLOSED_CONTEXT)
    with caplog.at_level(logging.WARNING, logger="app.api.chat"):
        response = client.post(
            "/chat", json={"hotel_id": "h1", "region": "nahariya", "question": "Meat restaurant?"}
        )
    assert "Crazy Bar" not in response.json()["text"]
    assert len(engine.calls) == 2
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_chat_no_retry_when_context_has_no_closed_entries(client):
    fake_engine = override_with_fakes(context="no closed entries here")
    client.post(
        "/chat", json={"hotel_id": "h1", "region": "nahariya", "question": "Meat restaurant?"}
    )
    assert len(fake_engine.calls) == 1


def test_closed_business_word_boundary_avoids_false_positive():
    patterns = _closed_business_patterns(
        "### Bar\ncategory: closed | region: נהריה | updated: 2026-10-11\nClosed."
    )
    assert _find_closed_mention("I enjoyed Barcelona", patterns) is None


def test_closed_business_name_variant_without_parenthetical_detected():
    patterns = _closed_business_patterns(
        "### Sogo (Kosher Bistro Bar)\ncategory: closed | region: נהריה | updated: 2026-10-11\n"
        "Closed."
    )
    assert _find_closed_mention("I recommend Sogo for dinner", patterns) == "Sogo (Kosher Bistro Bar)"
