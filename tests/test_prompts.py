from app.models.hotel_settings import PresentationMode
from app.prompts import build_system_prompt


def test_website_mode_never_mentions_front_desk():
    assert "front desk" not in build_system_prompt(PresentationMode.website)


def test_hotel_mode_mentions_front_desk():
    assert "front desk" in build_system_prompt(PresentationMode.hotel)


def test_hotel_demo_mode_mentions_front_desk():
    assert "front desk" in build_system_prompt(PresentationMode.hotel_demo)


def test_default_mode_is_website():
    assert build_system_prompt() == build_system_prompt(PresentationMode.website)


def test_instructs_searching_before_giving_up():
    # The actual bug report: the model gave up with a generic non-answer
    # instead of trying web_search first for a question search could answer.
    prompt = build_system_prompt(PresentationMode.website)
    assert "web_search" in prompt
    assert prompt.index("web_search") < prompt.index("do not have a specific recommendation")


def test_instructs_checking_closed_businesses_list():
    # Bug report: the bot recommended businesses (Sogo, Crazy Bar) that had
    # actually closed years ago — the knowledge base now carries a
    # category: closed list, and the model must be told to check it.
    prompt = build_system_prompt()
    assert "category: closed" in prompt
    assert "Never recommend it" in prompt


def test_instructs_recency_caveat_for_unconfirmed_businesses():
    # Bug report: the bot stated unverified business info (e.g. a bar that
    # may or may not still be open) as settled fact instead of flagging it.
    prompt = build_system_prompt()
    assert "updated date" in prompt
    assert "verify it is still open" in prompt
