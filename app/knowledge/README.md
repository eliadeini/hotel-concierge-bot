# `app/knowledge/` — knowledge-source abstraction

## Why this exists
Local knowledge currently lives in Markdown files under `files/`, but the
real long-term asset is the *content*, not the storage format — the plan
is to eventually move to a database-backed source once the skill files
grow large enough to need real querying. So `app/api/chat.py` never reads
the filesystem directly — it only calls `KnowledgeSource.get_context(...)`.
A future `PostgresSource` is a swap of implementation behind that
interface, not a refactor of the endpoint.

## Layout
- **`base.py`** — the `KnowledgeSource` interface. `get_context(hotel_id,
  region, category=None)` returns the concatenated knowledge entries for a
  region as one string; an empty string means "no local knowledge".
- **`markdown_source.py`** — `MarkdownFileSource`, the only implementation
  right now. Reads every `*.md` file under `files/{region}/`, parses one or
  more YAML-frontmatter entries per file, and concatenates the matching
  ones into a single context string.
- **`files/`** — the actual skill content, one subfolder per region
  (`nahariya/`, `eilat/`, `prague/` for manual testing, etc.). Each `.md`
  entry has `---` YAML frontmatter (`name`, `category`, `region`, `tags`,
  `updated`) followed by free-text body. The frontmatter is what will let
  a future DB migration be a script, not an LLM extraction job — the
  structure already exists.

## Notes
- Region values are restricted to a whitelist (`markdown_source.py`'s
  `_REGION_RE`: ASCII letters/digits/hyphen, the Hebrew Unicode block, and
  spaces) specifically to block path traversal via a malicious `region`
  parameter — no ".", "/", "\", or control characters can ever match.
  Hebrew is deliberately included: region tags are meant to be real Hebrew
  place names (e.g. `"גליל מערבי"`), not transliterated slugs — the
  ASCII-only default was a defensive choice, not a requirement that tags
  be in English.
- A `.md` file with no frontmatter at all is still accepted — it's treated
  as a single entry with empty metadata.

## Hotel skill files
- **`hotel_skill.py`** — `read_hotel_skill(path)`, unrelated to region
  knowledge: reads a single hotel's free-text "skill" file (tone/branding
  instructions + WhatsApp onboarding greeting), pointed to by
  `HotelSettings.hotel_skill_path`. Read fresh on every call, no caching,
  same as the region files. Returns `None` if unset or missing, so callers
  fall back to generic defaults.
- **`hotel_skills/`** — where hotel skill files conventionally live (e.g.
  `hotel_skills/example.md` is a reference/template, not wired to any
  hotel by default). `hotel_skill_path` can point anywhere, but this is
  the suggested location for new ones.