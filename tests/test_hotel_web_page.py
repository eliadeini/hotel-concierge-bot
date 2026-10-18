import json

from app.models.conversation_log import ConversationLog
from app.models.hotel_region_tag import HotelRegionTag
from app.models.hotel_settings import AIEngineType, HotelSettings, PresentationMode
from app.models.hotel_web_page import HotelWebPage
from app.security.crypto import encrypt_key
from app.ui import routes as ui_routes
from tests.conftest import FakeEngine

HEADERS = {"X-Admin-Token": "test-admin-token"}


def add_hotel(db, hotel_id, tags=(), presentation_mode=PresentationMode.website, is_test=False):
    hotel = HotelSettings(
        hotel_id=hotel_id,
        ai_engine=AIEngineType.openai,
        api_key_encrypted=encrypt_key("k"),
        presentation_mode=presentation_mode,
        is_test=is_test,
    )
    db.add(hotel)
    db.commit()
    for tag in tags:
        db.add(HotelRegionTag(hotel_settings_id=hotel.id, tag=tag))
    db.commit()
    return hotel


def add_web_page(db, hotel, **overrides):
    # display_name/tagline/page_title are stored as JSON — see
    # HotelWebPage.pick_language — so direct-DB-insert tests must encode
    # them the same way the admin endpoint would.
    defaults = dict(
        hotel_settings_id=hotel.id,
        location="beachtown",
        slug="demo",
        display_name=json.dumps({"he": "מלון לדוגמה", "en": "Example Hotel"}, ensure_ascii=False),
        tagline=json.dumps({"he": "שאלו אותי כל דבר"}, ensure_ascii=False),
        page_title=json.dumps(
            {"he": "מלון לדוגמה - קונסיירז'", "en": "Example Hotel - Concierge"},
            ensure_ascii=False,
        ),
        logo_file=None,
        background_file=None,
        enabled=True,
    )
    defaults.update(overrides)
    page = HotelWebPage(**defaults)
    db.add(page)
    db.commit()
    return page


def web_page_payload(**overrides):
    payload = {
        "location": "beachtown",
        "slug": "demo",
        "display_name": {"he": "מלון לדוגמה", "en": "Example Hotel"},
        "tagline": {"he": "תג עדכני", "en": "Updated tagline"},
        "page_title": {"he": "עמוד בדיקה", "en": "Test Page"},
    }
    payload.update(overrides)
    return payload


def patch_fake_engine(monkeypatch, found_in_kb=True):
    fake_engine = FakeEngine(found_in_kb=found_in_kb)
    monkeypatch.setattr(ui_routes.engine_factory, "get_engine", lambda hotel_id, db: fake_engine)
    return fake_engine


# --- GET /chatbot/{location}/{slug} -----------------------------------------


def test_hotel_web_page_renders_with_row_values(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Example Hotel" in response.text
    assert "<title>Example Hotel - Concierge" in response.text
    assert "/chatbot/beachtown/demo/ask" in response.text


def test_hotel_web_page_defaults_to_english(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo")

    assert 'lang="en"' in response.text
    assert "Example Hotel" in response.text
    assert "מלון לדוגמה" not in response.text


def test_hotel_web_page_lang_en_shows_english(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo?lang=en")

    assert 'lang="en"' in response.text
    assert "Example Hotel" in response.text
    assert "Example Hotel - Concierge" in response.text
    assert "מלון לדוגמה" not in response.text


def test_hotel_web_page_lang_he_shows_hebrew(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo?lang=he")

    assert 'lang="he"' in response.text
    assert "מלון לדוגמה" in response.text
    assert "שאלו אותי כל דבר" in response.text
    assert "Example Hotel" not in response.text


def test_hotel_web_page_lang_en_falls_back_to_hebrew_for_missing_field(client, db):
    # The fixture's tagline only has an "he" entry — ?lang=en must still
    # show it (via pick_language's fallback) rather than erroring or
    # showing nothing.
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo?lang=en")

    assert "שאלו אותי כל דבר" in response.text


def test_hotel_web_page_unrecognized_lang_falls_back_to_english(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo?lang=fr")

    assert response.status_code == 200
    assert 'lang="en"' in response.text
    assert "Example Hotel" in response.text


def test_hotel_web_page_escapes_html_in_display_name(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(
        db,
        hotel,
        display_name=json.dumps(
            {"he": '<script>alert(1)</script> & "co"'}, ensure_ascii=False
        ),
    )

    response = client.get("/chatbot/beachtown/demo")

    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_hotel_web_page_renders_logo_and_background(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel, logo_file="logo.png", background_file="bg.jpg")

    response = client.get("/chatbot/beachtown/demo")

    assert response.status_code == 200
    assert "/hotel-assets/hotel-example/logo.png" in response.text
    assert "/hotel-assets/hotel-example/bg.jpg" in response.text
    assert 'class="site-logo"' in response.text


def test_hotel_web_page_no_logo_renders_empty_slot(client, db):
    # "site-logo" alone would also match the template's static CSS rule
    # (.site-logo { ... }), which exists regardless of whether a logo is
    # actually used — check for the rendered <img> specifically instead.
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo")

    assert "<img" not in response.text


def test_hotel_web_page_logo_links_to_website_url_when_set(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(
        db, hotel, logo_file="logo.png", website_url="https://example-hotel.test/"
    )

    response = client.get("/chatbot/beachtown/demo")

    assert response.status_code == 200
    assert '<a href="https://example-hotel.test/"' in response.text
    assert "<img" in response.text


def test_hotel_web_page_logo_not_linked_when_website_url_absent(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel, logo_file="logo.png")

    response = client.get("/chatbot/beachtown/demo")

    # target="_blank" only ever appears on the website_url-wrapping anchor
    # (see hotel_web_page()'s logo_html build) — its absence confirms the
    # logo stayed a plain, unwrapped <img>.
    assert 'target="_blank"' not in response.text
    assert "<img" in response.text


def test_hotel_web_page_never_shows_about_button(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo")

    assert "/about" not in response.text


def test_hotel_web_page_unknown_location_slug_returns_404(client):
    response = client.get("/chatbot/nowhere/nothing")
    assert response.status_code == 404


def test_hotel_web_page_disabled_returns_404(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel, enabled=False)

    response = client.get("/chatbot/beachtown/demo")

    assert response.status_code == 404


def test_hotel_web_page_test_hotel_returns_404(client, db):
    hotel = add_hotel(db, "hotel-example", is_test=True)
    add_web_page(db, hotel)

    response = client.get("/chatbot/beachtown/demo")

    assert response.status_code == 404


# --- POST /chatbot/{location}/{slug}/ask ------------------------------------


def test_hotel_web_page_ask_reaches_right_hotel(client, db, monkeypatch):
    hotel = add_hotel(db, "hotel-example", tags=["nahariya"])
    add_web_page(db, hotel)
    fake_engine = patch_fake_engine(monkeypatch, found_in_kb=True)

    response = client.post("/chatbot/beachtown/demo/ask", json={"question": "Where to eat?"})

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "echo: Where to eat?"
    assert body["found_in_kb"] is True
    assert len(fake_engine.calls) == 1


def test_hotel_web_page_ask_logs_conversation_with_hotel_id(client, db, monkeypatch):
    hotel = add_hotel(db, "hotel-example", tags=["nahariya"])
    add_web_page(db, hotel)
    patch_fake_engine(monkeypatch)

    client.post("/chatbot/beachtown/demo/ask", json={"question": "hi"})

    logs = db.query(ConversationLog).all()
    assert len(logs) == 1
    assert logs[0].hotel_id == "hotel-example"
    assert logs[0].question == "hi"


def test_hotel_web_page_ask_unknown_page_returns_404(client):
    response = client.post("/chatbot/nowhere/nothing/ask", json={"question": "hi"})
    assert response.status_code == 404


def test_hotel_web_page_ask_disabled_page_returns_404(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel, enabled=False)

    response = client.post("/chatbot/beachtown/demo/ask", json={"question": "hi"})

    assert response.status_code == 404


def test_hotel_web_page_ask_test_hotel_returns_404(client, db):
    hotel = add_hotel(db, "hotel-example", is_test=True)
    add_web_page(db, hotel)

    response = client.post("/chatbot/beachtown/demo/ask", json={"question": "hi"})

    assert response.status_code == 404


# --- POST /admin/hotels with nested web_page --------------------------------


def test_admin_create_hotel_with_web_page(client, db):
    response = client.post(
        "/admin/hotels",
        json={
            "hotel_id": "hotel-example",
            "ai_engine": "openai",
            "api_key": "sk-test",
            "web_page": web_page_payload(),
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["web_page"]["url"] == "/chatbot/beachtown/demo"
    assert body["web_page"]["display_name"] == {"he": "מלון לדוגמה", "en": "Example Hotel"}

    row = db.query(HotelWebPage).filter_by(location="beachtown", slug="demo").one()
    assert json.loads(row.display_name) == {"he": "מלון לדוגמה", "en": "Example Hotel"}


def test_admin_create_hotel_without_web_page_omits_it(client):
    response = client.post(
        "/admin/hotels",
        json={"hotel_id": "hotel-example", "ai_engine": "openai", "api_key": "sk-test"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert "web_page" not in response.json()


def test_admin_hotels_missing_token_rejected(client):
    response = client.post(
        "/admin/hotels",
        json={"hotel_id": "hotel-example", "ai_engine": "openai", "api_key": "sk-test"},
    )
    assert response.status_code == 401


# --- PUT /admin/hotels/{hotel_id}/web-page ----------------------------------


def test_admin_web_page_unknown_hotel_returns_404(client):
    response = client.put(
        "/admin/hotels/no-such-hotel/web-page", json=web_page_payload(), headers=HEADERS
    )
    assert response.status_code == 404


def test_admin_web_page_missing_token_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put("/admin/hotels/hotel-example/web-page", json=web_page_payload())
    assert response.status_code == 401


def test_admin_web_page_wrong_token_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(),
        headers={"X-Admin-Token": "wrong"},
    )
    assert response.status_code == 401


def test_admin_web_page_updates_in_place(client, db):
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(display_name={"he": "שם חדש"}),
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == {"he": "שם חדש"}
    rows = db.query(HotelWebPage).filter_by(hotel_settings_id=hotel.id).all()
    assert len(rows) == 1  # updated in place, not duplicated
    assert json.loads(rows[0].display_name) == {"he": "שם חדש"}


def test_admin_web_page_conflict_with_other_hotel_returns_409(client, db):
    hotel_a = add_hotel(db, "hotel-a")
    add_web_page(db, hotel_a, location="beachtown", slug="demo")
    add_hotel(db, "hotel-b")

    response = client.put(
        "/admin/hotels/hotel-b/web-page",
        json=web_page_payload(location="beachtown", slug="demo"),
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_admin_web_page_same_hotel_reusing_its_own_path_not_a_conflict(client, db):
    # A hotel updating its own page with its own existing location+slug
    # must not 409 against itself.
    hotel = add_hotel(db, "hotel-example")
    add_web_page(db, hotel)

    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(display_name={"he": "עדכון"}),
        headers=HEADERS,
    )

    assert response.status_code == 200


def test_admin_web_page_invalid_location_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(location="Bad Location!"),
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_admin_web_page_invalid_slug_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(slug="UPPER"),
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_admin_web_page_logo_filename_with_traversal_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(logo_file="../../etc/passwd"),
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_admin_web_page_background_filename_with_slash_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(background_file="a/b.png"),
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_admin_web_page_missing_hebrew_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(display_name={"en": "English only"}),
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_admin_web_page_unsupported_language_key_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(tagline={"he": "שלום", "fr": "Bonjour"}),
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_admin_web_page_english_only_field_is_allowed(client, db):
    # "en" is optional per-field as long as "he" is present somewhere in
    # the payload — a field with only "he" (no "en" at all) is valid.
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(tagline={"he": "רק עברית"}),
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["tagline"] == {"he": "רק עברית"}


def test_admin_web_page_website_url_round_trips(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(website_url="https://example-hotel.test/"),
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["website_url"] == "https://example-hotel.test/"

    row = db.query(HotelWebPage).filter_by(location="beachtown", slug="demo").one()
    assert row.website_url == "https://example-hotel.test/"


def test_admin_web_page_website_url_omitted_stays_none(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page", json=web_page_payload(), headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json()["website_url"] is None


def test_admin_web_page_website_url_without_scheme_rejected(client, db):
    add_hotel(db, "hotel-example")
    response = client.put(
        "/admin/hotels/hotel-example/web-page",
        json=web_page_payload(website_url="example-hotel.test"),
        headers=HEADERS,
    )
    assert response.status_code == 422
