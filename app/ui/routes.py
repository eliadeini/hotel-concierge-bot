"""FastAPI routes for the WhatsApp-lookalike browser demo.

Reuses the exact same context-gathering and AI-answering logic the real
WhatsApp path uses (app.messaging.inbound.gather_context,
app.api.chat.answer_question) — this is not a separate/divergent
implementation, so what's shown here is provably what a real WhatsApp
message would get. See README.md in this folder for why this exists.
"""

import html
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.chat import ChatResponse, answer_question
from app.config import UIMode, settings
from app.db import get_db
from app.engines import factory as engine_factory
from app.messaging.inbound import gather_context
from app.models.hotel_settings import HotelSettings
from app.models.hotel_web_page import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, HotelWebPage, pick_language
from app.models.user_note import UserNoteSentiment
from app.ui.strings import ABOUT_STRINGS, UI_STRINGS
from app.user_notes import submit_user_note

router = APIRouter()

# Hardcoded tenants for now — the first thing to generalize (e.g. a
# ?hotel_id= / path param) once this grows to serve more than one hotel or
# more than one location. DEMO_HOTEL_ID (PresentationMode.hotel_demo) backs
# the WhatsApp-lookalike hotel demo; NAHARIYA_GUIDE_HOTEL_ID
# (PresentationMode.website) is a separate tenant backing the general
# public site — kept separate specifically so shared knowledge content can
# be neutralized for the public tenant without affecting the hotel demo
# (see app/messaging/inbound.py::gather_context).
DEMO_HOTEL_ID = "hotel-demo"
NAHARIYA_GUIDE_HOTEL_ID = "nahariya-guide"

_DEMO_HTML = (Path(__file__).parent / "templates" / "demo.html").read_text(encoding="utf-8")

# Raw template with __TOKEN__ placeholders, not ready-to-serve HTML on its
# own — see _render_website_page below. Shared by the fixed nahariya page
# and every generic /chatbot/{location}/{slug} page.
_WEBSITE_TEMPLATE = (
    Path(__file__).parent / "templates" / "website.html"
).read_text(encoding="utf-8")

_ACCESSIBILITY_HTML = (
    Path(__file__).parent / "templates" / "accessibility.html"
).read_text(encoding="utf-8")

_PRIVACY_HTML = (Path(__file__).parent / "templates" / "privacy.html").read_text(encoding="utf-8")

_TERMS_HTML = (Path(__file__).parent / "templates" / "terms.html").read_text(encoding="utf-8")

# Raw template with __TOKEN__ placeholders — see _render_about_page below.
_ABOUT_TEMPLATE = (Path(__file__).parent / "templates" / "about.html").read_text(encoding="utf-8")

# Served from the gitignored /private-assets mount (app/main.py), not
# /static — see app/ui/README.md's "About page" section for why.
_ABOUT_PHOTO_URL = "/private-assets/about-photo.jpeg"


class DemoAskRequest(BaseModel):
    question: str = Field(min_length=1)


class NoteRequest(BaseModel):
    conversation_id: int
    message: str | None = None
    sentiment: UserNoteSentiment | None = None

    @model_validator(mode="after")
    def _require_content(self):
        if self.message is None and self.sentiment is None:
            raise ValueError("Provide a message, a sentiment, or both.")
        return self


def _render_website_page(
    *,
    page_title: str,
    site_name: str,
    tagline: str,
    bg_image_url: str,
    logo_html: str,
    ask_url: str,
    lang: str = DEFAULT_LANGUAGE,
    about_button_html: str = "",
) -> str:
    """Fills _WEBSITE_TEMPLATE's __TOKEN__ placeholders via str.replace —
    not str.format, since the CSS is full of literal braces that would
    collide with format's own {}/{{}} syntax.

    Callers are responsible for html.escape()-ing any value that came from
    the database before passing it in here — this function does no
    escaping itself, since the fixed nahariya/demo-style callers pass
    their own literal (not DB-sourced) strings unescaped on purpose.

    `lang` sets the <html lang="..."> attribute and selects which
    language's chrome text (UI_STRINGS, app/ui/strings.py) is used for the
    input placeholder, error messages, and footer links — it does not
    otherwise change the page's layout; there's no RTL/LTR-specific CSS in
    this template to flip either way.

    `about_button_html` is opaque pre-built HTML (same pattern as
    logo_html), empty by default — only nahariya_chatbot_page() passes a
    real one. Generic hotel pages (hotel_web_page()) deliberately leave
    this empty: that header slot is used for the hotel's own
    website-link-wrapped logo instead (see HotelWebPage.website_url).
    """
    ui = UI_STRINGS.get(lang, UI_STRINGS[DEFAULT_LANGUAGE])
    return (
        _WEBSITE_TEMPLATE.replace("__PAGE_TITLE__", page_title)
        .replace("__SITE_NAME__", site_name)
        .replace("__TAGLINE__", tagline)
        .replace("__BG_IMAGE_URL__", bg_image_url)
        .replace("__LOGO__", logo_html)
        .replace("__ASK_URL__", ask_url)
        .replace("__LANG__", lang)
        .replace("__ABOUT_BUTTON__", about_button_html)
        .replace("__QUESTION_LABEL__", ui["question_label"])
        .replace("__PLACEHOLDER__", ui["placeholder"])
        .replace("__SEND_ARIA_LABEL__", ui["send_aria_label"])
        .replace("__SEND_TITLE__", ui["send_title"])
        .replace("__ERROR_NO_ANSWER__", ui["error_no_answer"])
        .replace("__ERROR_NETWORK__", ui["error_network"])
        .replace("__FOOTER_ACCESSIBILITY__", ui["footer_accessibility"])
        .replace("__FOOTER_PRIVACY__", ui["footer_privacy"])
        .replace("__FOOTER_TERMS__", ui["footer_terms"])
    )


def _ask(hotel_id: str, question: str, db: Session) -> ChatResponse:
    """Shared by both browser ask endpoints below — hotel lookup,
    gather_context, answer_question, mirroring
    app.messaging.inbound.process_inbound_message's sequence but stopping
    short of the WhatsApp-provider send step and returning the text
    directly instead.

    Deliberately skips GuestSession/flow_state routing (app/messaging/flow.py):
    there's no "checked in via WhatsApp" concept for a browser page, so this
    always goes straight to the AI-engine path.
    """
    hotel = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
    if hotel is None:
        raise HTTPException(
            status_code=503,
            detail=f"Tenant {hotel_id!r} not seeded — see app/ui/README.md",
        )

    region_label, context = gather_context(hotel)
    try:
        result, conversation_id = answer_question(
            hotel_id, region_label, question, context, db, engine_factory.get_engine
        )
    except engine_factory.UnknownHotelError:
        raise HTTPException(status_code=404, detail="Unknown hotel_id")

    return ChatResponse(
        text=result.text, found_in_kb=result.found_in_kb, conversation_id=conversation_id
    )


@router.get("/demo", response_class=HTMLResponse)
def demo_page() -> str:
    """Always the hotel-lookalike look, regardless of UIMode — kept
    reachable on its own fixed path for demoing to prospective hotel
    clients even while the site's default (GET /) is in website mode."""
    return _DEMO_HTML


@router.get("/chatbot/nahariya", response_class=HTMLResponse)
def nahariya_chatbot_page() -> str:
    """The general public website look for Nahariya. Path is
    location-scoped (/chatbot/<location>) rather than a flat /website so
    other locations can get their own page later (/chatbot/eilat, etc.)
    without reshuffling this one's URL. Fixed/hardcoded values here (not
    DB-sourced, so not html.escape()'d) — must keep rendering byte-for-byte
    what this page looked like before /chatbot/{location}/{slug} existed,
    aside from the new About button (see _render_website_page's
    about_button_html docs)."""
    about_label = UI_STRINGS["he"]["about_button"]
    return _render_website_page(
        page_title="נהרייני - מדריך נהרייני מקומי",
        site_name="נהרייני",
        tagline=(
            "מדריך נהרייני מקומי — שאלו אותי כל דבר על ביקור בנהריה: "
            "חופים, מסעדות, טיולים ועוד"
        ),
        bg_image_url="/static/Nahariya-bg.jpg",
        logo_html="",
        ask_url="/chatbot/nahariya/ask",
        lang="he",
        about_button_html=f'<a href="/about?lang=he" class="about-button">{about_label}</a>',
    )


@router.get("/chatbot/{location}/{slug}", response_class=HTMLResponse)
def hotel_web_page(
    location: str, slug: str, lang: str = DEFAULT_LANGUAGE, db: Session = Depends(get_db)
) -> str:
    """Generic, DB-configured hotel page — see HotelWebPage. Registered
    after the fixed /chatbot/nahariya route above; no actual path-collision
    risk either way (that route is 1 segment, this one requires 2), but
    kept in this order regardless. 404 is identical whether the page is
    missing, disabled, or belongs to a test hotel — never distinguishes, so
    a prober can't tell "never existed" apart from "exists but disabled".

    ?lang=he/en picks which language's text to show (see
    HotelWebPage.pick_language) — an unrecognized/missing value silently
    falls back to DEFAULT_LANGUAGE rather than erroring, since this is a
    cosmetic query param on a public page, not something worth 4xx-ing a
    guest over."""
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    row = db.query(HotelWebPage).filter_by(location=location, slug=slug).one_or_none()
    if row is None or not row.enabled:
        raise HTTPException(status_code=404, detail="Unknown hotel page")
    hotel = db.query(HotelSettings).filter_by(id=row.hotel_settings_id).one_or_none()
    if hotel is None or hotel.is_test:
        raise HTTPException(status_code=404, detail="Unknown hotel page")

    display_name = pick_language(row.display_name, lang)

    logo_html = ""
    if row.logo_file:
        logo_src = html.escape(f"/hotel-assets/{hotel.hotel_id}/{row.logo_file}")
        logo_alt_prefix = UI_STRINGS.get(lang, UI_STRINGS[DEFAULT_LANGUAGE])["logo_alt_prefix"]
        alt = html.escape(f"{logo_alt_prefix} {display_name}")
        logo_html = f'<img src="{logo_src}" alt="{alt}" class="site-logo">'
        if row.website_url:
            href = html.escape(row.website_url)
            logo_html = f'<a href="{href}" target="_blank" rel="noopener noreferrer">{logo_html}</a>'

    bg_image_url = ""
    if row.background_file:
        bg_image_url = html.escape(f"/hotel-assets/{hotel.hotel_id}/{row.background_file}")

    return _render_website_page(
        page_title=html.escape(pick_language(row.page_title, lang)),
        site_name=html.escape(display_name),
        tagline=html.escape(pick_language(row.tagline, lang)),
        bg_image_url=bg_image_url,
        logo_html=logo_html,
        ask_url=f"/chatbot/{location}/{slug}/ask",
        lang=lang,
    )


@router.get("/accessibility", response_class=HTMLResponse)
def accessibility_page() -> str:
    """The accessibility statement required by regulation 35(ה) to the
    Equal Rights for Persons with Disabilities (Service Accessibility
    Adaptations) Regulations, 5773-2013 — linked from the footer of both
    /demo and /chatbot/nahariya."""
    return _ACCESSIBILITY_HTML


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page() -> str:
    """The privacy policy required by the notice duty in section 11 of the
    Protection of Privacy Law, 5741-1981 (as amended by Amendment 13) —
    linked from the footer of both /demo and /chatbot/nahariya."""
    return _PRIVACY_HTML


@router.get("/terms", response_class=HTMLResponse)
def terms_page() -> str:
    """Terms of use: nature of the free informational service, content-
    accuracy disclaimer, and no-liability-for-recommended-businesses clause
    — linked from the footer of both /demo and /chatbot/nahariya."""
    return _TERMS_HTML


def _render_about_page(lang: str) -> str:
    """Fills _ABOUT_TEMPLATE's __TOKEN__ placeholders — same str.replace()
    pattern as _render_website_page. Content comes from ABOUT_STRINGS
    (app/ui/strings.py); the photo is a literal constant, not DB-sourced,
    so nothing here needs html.escape()."""
    content = ABOUT_STRINGS.get(lang, ABOUT_STRINGS[DEFAULT_LANGUAGE])
    return (
        _ABOUT_TEMPLATE.replace("__LANG__", lang)
        .replace("__PAGE_TITLE__", content["page_title"])
        .replace("__PHOTO_URL__", _ABOUT_PHOTO_URL)
        .replace("__PHOTO_ALT__", content["photo_alt"])
        .replace("__HEADING__", content["heading"])
        .replace("__BIO_HTML__", content["bio_html"])
        .replace("__BACK_LINK_TEXT__", content["back_link_text"])
    )


@router.get("/about", response_class=HTMLResponse)
def about_page(lang: str = DEFAULT_LANGUAGE) -> str:
    """A personal page about the site's developer/the project — not tied to
    any hotel's data. Meant as a stable, linkable URL (e.g. for a CV), so
    its path/behavior should stay simple and not grow DB-dependent.
    ?lang=he/en picks the language, same convention and same silent
    fallback-to-default as hotel_web_page(). Linked from a small button in
    /demo's and /chatbot/nahariya's header — deliberately NOT linked from
    generic hotel pages (/chatbot/{location}/{slug}), which use that same
    header slot for a link to the hotel's own website instead (see
    HotelWebPage.website_url / hotel_web_page() above)."""
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    return _render_about_page(lang)


@router.get("/", include_in_schema=False)
def index_page() -> RedirectResponse:
    """Redirect target is config-driven (settings.ui_mode), so the same
    deployment can be flipped between "general public website" and "hotel
    demo" as its default front door without a code change. /demo and
    /chatbot/nahariya are both reachable directly either way."""
    target = "/chatbot/nahariya" if settings.ui_mode == UIMode.website else "/demo"
    return RedirectResponse(url=target)


@router.post("/demo/ask", response_model=ChatResponse)
def demo_ask(req: DemoAskRequest, db: Session = Depends(get_db)) -> ChatResponse:
    return _ask(DEMO_HOTEL_ID, req.question, db)


@router.post("/chatbot/nahariya/ask", response_model=ChatResponse)
def nahariya_chatbot_ask(req: DemoAskRequest, db: Session = Depends(get_db)) -> ChatResponse:
    return _ask(NAHARIYA_GUIDE_HOTEL_ID, req.question, db)


@router.post("/chatbot/{location}/{slug}/ask", response_model=ChatResponse)
def hotel_web_page_ask(
    location: str, slug: str, req: DemoAskRequest, db: Session = Depends(get_db)
) -> ChatResponse:
    """Same lookup/404 rules as GET hotel_web_page above, then the usual
    _ask() with that row's own hotel_id."""
    row = db.query(HotelWebPage).filter_by(location=location, slug=slug).one_or_none()
    if row is None or not row.enabled:
        raise HTTPException(status_code=404, detail="Unknown hotel page")
    hotel = db.query(HotelSettings).filter_by(id=row.hotel_settings_id).one_or_none()
    if hotel is None or hotel.is_test:
        raise HTTPException(status_code=404, detail="Unknown hotel page")
    return _ask(hotel.hotel_id, req.question, db)


@router.post("/notes")
def submit_note(req: NoteRequest, db: Session = Depends(get_db)) -> dict:
    """Guest reaction (like/dislike and/or free text) to a specific
    exchange — shared by the demo and website chat UIs. Not tenant-scoped:
    conversation_id already identifies which hotel the note belongs to.
    See app/user_notes.py."""
    try:
        note = submit_user_note(
            req.conversation_id, "website", db, message=req.message, sentiment=req.sentiment
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Unknown conversation_id")
    return {"id": note.id}