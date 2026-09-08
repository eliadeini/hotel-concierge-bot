from app.api.chat import get_engine_factory, get_knowledge_source
from app.main import app
from app.models.conversation_log import ConversationLog
from tests.conftest import FakeEngine, FakeKnowledgeSource


def override_with_fakes(found_in_kb=True, context="fake knowledge context"):
    fake_engine = FakeEngine(found_in_kb=found_in_kb)
    app.dependency_overrides[get_knowledge_source] = lambda: FakeKnowledgeSource(context)
    app.dependency_overrides[get_engine_factory] = lambda: (
        lambda hotel_id, db: fake_engine
    )
    return fake_engine


def test_chat_happy_path(client):
    override_with_fakes(found_in_kb=True)
    response = client.post(
        "/chat",
        json={"hotel_id": "h1", "region": "nahariya", "question": "Where to eat?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"text": "echo: Where to eat?", "found_in_kb": True}


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
