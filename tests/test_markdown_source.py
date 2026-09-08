from app.knowledge.markdown_source import MarkdownFileSource

SINGLE_ENTRY = """\
---
region: testville
category: attractions
name: The Waterfall
tags: [nature, easy]
updated: 2026-07-13
---
A gentle hike next to the waterfall.
"""

MULTI_ENTRY = """\
---
category: restaurants
name: Cafe One
---
Great breakfast spot.

---
category: restaurants
name: Grill Two
---
Steakhouse near the beach.
"""


def make_source(tmp_path, region="testville", files=None):
    region_dir = tmp_path / region
    region_dir.mkdir()
    for filename, content in (files or {}).items():
        (region_dir / filename).write_text(content, encoding="utf-8")
    return MarkdownFileSource(base_dir=tmp_path)


def test_single_entry_parsed(tmp_path):
    source = make_source(tmp_path, files={"attractions.md": SINGLE_ENTRY})
    context = source.get_context("h1", "testville")
    assert "The Waterfall" in context
    assert "gentle hike" in context
    assert "nature" in context


def test_multiple_entries_in_one_file(tmp_path):
    source = make_source(tmp_path, files={"restaurants.md": MULTI_ENTRY})
    context = source.get_context("h1", "testville")
    assert "Cafe One" in context
    assert "Grill Two" in context


def test_category_filter(tmp_path):
    source = make_source(
        tmp_path,
        files={"attractions.md": SINGLE_ENTRY, "restaurants.md": MULTI_ENTRY},
    )
    context = source.get_context("h1", "testville", category="restaurants")
    assert "Cafe One" in context
    assert "The Waterfall" not in context


def test_unknown_region_returns_empty(tmp_path):
    source = make_source(tmp_path, files={"attractions.md": SINGLE_ENTRY})
    assert source.get_context("h1", "nowhere") == ""


def test_path_traversal_blocked(tmp_path):
    source = make_source(tmp_path, files={"attractions.md": SINGLE_ENTRY})
    assert source.get_context("h1", "../testville") == ""
    assert source.get_context("h1", "..") == ""
    assert source.get_context("h1", "") == ""


def test_hebrew_region_name_supported(tmp_path):
    """Region tags are meant to be real Hebrew place names (e.g. "גליל
    מערבי"), not transliterated slugs — see the _REGION_RE comment in
    markdown_source.py."""
    source = make_source(tmp_path, region="גליל מערבי", files={"attractions.md": SINGLE_ENTRY})
    context = source.get_context("h1", "גליל מערבי")
    assert "The Waterfall" in context


def test_path_traversal_still_blocked_alongside_hebrew(tmp_path):
    """Widening _REGION_RE to accept Hebrew must not reopen traversal."""
    source = make_source(tmp_path, files={"attractions.md": SINGLE_ENTRY})
    assert source.get_context("h1", "../גליל מערבי") == ""
    assert source.get_context("h1", "גליל מערבי/../secret") == ""


def test_file_without_frontmatter(tmp_path):
    source = make_source(tmp_path, files={"notes.md": "Just some plain notes."})
    assert "plain notes" in source.get_context("h1", "testville")


def test_bundled_regions_load():
    """The real seed files under app/knowledge/files parse without errors."""
    source = MarkdownFileSource()
    assert "ראש הנקרה" in source.get_context("h1", "nahariya")
    assert "כופתאות הוולטבה המוזהבות" in source.get_context("h1", "prague")
    assert "יאללה גליל" in source.get_context("h1", "גליל מערבי")
