from app.api.chat import get_engine_factory, get_knowledge_source
from app.main import app
from app.models.user_note import UserNote, UserNoteStatus
from tests.conftest import FakeEngine, FakeKnowledgeSource

HEADERS = {"X-Admin-Token": "test-admin-token"}


def _make_conversation(client) -> int:
    """Creates a real ConversationLog row via /chat and returns its id."""
    app.dependency_overrides[get_knowledge_source] = lambda: FakeKnowledgeSource("ctx")
    app.dependency_overrides[get_engine_factory] = lambda: (
        lambda hotel_id, db: FakeEngine(found_in_kb=True)
    )
    response = client.post(
        "/chat", json={"hotel_id": "h1", "region": "nahariya", "question": "hi"}
    )
    return response.json()["conversation_id"]


def test_submit_note_with_message(client, db):
    conversation_id = _make_conversation(client)

    response = client.post(
        "/notes", json={"conversation_id": conversation_id, "message": "This looks wrong"}
    )

    assert response.status_code == 200
    note = db.query(UserNote).one()
    assert note.conversation_log_id == conversation_id
    assert note.channel == "website"
    assert note.message == "This looks wrong"
    assert note.sentiment is None
    assert note.status == UserNoteStatus.new


def test_submit_note_with_sentiment_only(client, db):
    conversation_id = _make_conversation(client)

    response = client.post("/notes", json={"conversation_id": conversation_id, "sentiment": "like"})

    assert response.status_code == 200
    note = db.query(UserNote).one()
    assert note.sentiment.value == "like"
    assert note.message is None


def test_submit_note_requires_message_or_sentiment(client):
    response = client.post("/notes", json={"conversation_id": 1})
    assert response.status_code == 422


def test_submit_note_unknown_conversation_returns_404(client):
    response = client.post("/notes", json={"conversation_id": 999999, "message": "hi"})
    assert response.status_code == 404


def test_admin_notes_requires_token(client):
    response = client.get("/admin/notes")
    assert response.status_code == 401


def test_admin_notes_wrong_token_rejected(client):
    response = client.get("/admin/notes", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 401


def test_admin_notes_lists_with_conversation_context(client, db):
    conversation_id = _make_conversation(client)
    client.post("/notes", json={"conversation_id": conversation_id, "message": "Suggest X"})

    response = client.get("/admin/notes", headers=HEADERS)

    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 1
    assert notes[0]["message"] == "Suggest X"
    assert notes[0]["status"] == "new"
    assert notes[0]["conversation"]["hotel_id"] == "h1"
    assert notes[0]["conversation"]["question"] == "hi"


def test_resolve_note(client, db):
    conversation_id = _make_conversation(client)
    client.post("/notes", json={"conversation_id": conversation_id, "sentiment": "dislike"})
    note_id = db.query(UserNote).one().id

    response = client.post(f"/admin/notes/{note_id}/resolve", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "reviewed"
    db.expire_all()
    assert db.query(UserNote).one().status == UserNoteStatus.reviewed


def test_resolve_unknown_note_returns_404(client):
    response = client.post("/admin/notes/999999/resolve", headers=HEADERS)
    assert response.status_code == 404