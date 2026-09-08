import re
from pathlib import Path

import yaml

from app.knowledge.base import KnowledgeSource

_DEFAULT_FILES_DIR = Path(__file__).parent / "files"

# Region names map to directory names — restrict to a safe charset so a
# malicious region value can never traverse the filesystem. A whitelist (no
# ".", "/", "\\", or control characters can ever match), not a blocklist.
# Written as ֐-׿ (Python re's own Unicode-escape syntax) rather
# than literal Hebrew characters in this pattern — RTL characters embedded
# directly in source are hard to visually verify and risk silent
# corruption. That range + space is included deliberately: region tags are
# meant to be real Hebrew place names (e.g. "גליל מערבי"), not
# transliterated slugs — restricting to ASCII-only was a defensive
# default, not a requirement that tags be in English.
_REGION_RE = re.compile(r"^[a-z0-9֐-׿\- ]+$")

# Matches one entry: a YAML frontmatter block followed by free text, up to the
# next frontmatter fence (supports multiple entries per file).
_ENTRY_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*?)(?=^---\s*\n|\Z)",
    re.MULTILINE | re.DOTALL,
)


class MarkdownFileSource(KnowledgeSource):
    """Reads knowledge entries from app/knowledge/files/{region}/*.md."""

    def __init__(self, base_dir: Path | str | None = None):
        self._base_dir = Path(base_dir) if base_dir else _DEFAULT_FILES_DIR

    def get_context(
        self, hotel_id: str, region: str, category: str | None = None
    ) -> str:
        if not region or not _REGION_RE.match(region):
            return ""
        region_dir = self._base_dir / region
        if not region_dir.is_dir():
            return ""

        entries: list[str] = []
        for md_file in sorted(region_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            for meta, body in self._parse_entries(text):
                if category and str(meta.get("category", "")) != category:
                    continue
                entries.append(self._format_entry(meta, body))
        return "\n\n".join(entries)

    @staticmethod
    def _parse_entries(text: str) -> list[tuple[dict, str]]:
        matches = list(_ENTRY_RE.finditer(text))
        if not matches:
            # File without frontmatter — treat the whole content as one entry.
            stripped = text.strip()
            return [({}, stripped)] if stripped else []

        entries = []
        for match in matches:
            try:
                meta = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            entries.append((meta, match.group(2).strip()))
        return entries

    @staticmethod
    def _format_entry(meta: dict, body: str) -> str:
        lines = []
        name = meta.get("name")
        if name:
            lines.append(f"### {name}")
        details = []
        for field in ("category", "region", "updated"):
            if meta.get(field):
                details.append(f"{field}: {meta[field]}")
        tags = meta.get("tags")
        if tags:
            if isinstance(tags, list):
                tags = ", ".join(str(t) for t in tags)
            details.append(f"tags: {tags}")
        if details:
            lines.append(" | ".join(details))
        if body:
            lines.append(body)
        return "\n".join(lines)
