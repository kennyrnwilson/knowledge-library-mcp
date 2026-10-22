"""add_quote: file a quote in its source's literature note, in the four-part shape.

The shape is the one in knowledge-library's `.templates/literature-summary.md`:

    > "The quote."
    > — Author, *Title*, location

    - **Why:** one line on why it mattered
    - **Links:** [Note](../../03-permanent-notes/x.md) · #quote/theme

Filesystem only, like the other write tools: nothing is committed until
`save_changes`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from knowledge_library_mcp.writer import _safe_join, slugify

LITERATURE_DIR = "02-literature-notes"
TEMPLATE = ".templates/literature-summary.md"
QUOTES_HEADING = "## 💬 Quotes & Highlights"

# Used when the library has no template, as in the test fixtures.
_FALLBACK_TEMPLATE = """# [Book/Article Title]

← [Back to Parent](./README.md)

**Author/Creator:** Name(s)
**Source Type:** Book | Article | Course | Video | Podcast

## 💬 Quotes & Highlights

---

**Tags:** #literature

*Created: YYYY-MM-DD*
*Last Updated: YYYY-MM-DD*
"""

_SOURCE_TYPES = {
    "books": "Book",
    "articles": "Article",
    "courses": "Course",
}

_QUOTES_SECTION = re.compile(r"^## .*Quotes & Highlights.*$", re.MULTILINE)
_LAST_UPDATED = re.compile(r"^\*Last [Uu]pdated: [^*]*\*$", re.MULTILINE)


def format_quote(
    text: str,
    author: str,
    title: str,
    location: str,
    why: str,
    themes: list[str] | None = None,
    links: list[str] | None = None,
) -> str:
    """Return one quote in the four-part shape, without surrounding blank lines."""
    text = text.strip().strip('"“”')
    if not text:
        raise ValueError("a quote needs its text")
    if not why.strip():
        raise ValueError("a quote needs a 'why': one line on why it mattered")
    source = f"— {author.strip()}, *{title.strip()}*"
    if location.strip():
        source += f", {location.strip()}"
    quoted = "\n".join(f"> {line}" if line else ">" for line in f'"{text}"'.splitlines())
    tags = [f"#quote/{slugify(t)}" for t in (themes or []) if t.strip()]
    link_parts = [link.strip() for link in (links or []) if link.strip()] + tags
    lines = [quoted, f"> {source}", "", f"- **Why:** {why.strip()}"]
    if link_parts:
        lines.append(f"- **Links:** {' · '.join(link_parts)}")
    return "\n".join(lines)


def insert_quote(note: str, block: str, today: str) -> str:
    """Append `block` to the end of the note's quotes section, adding one if missing."""
    match = _QUOTES_SECTION.search(note)
    if match is None:
        # Before the footer rule if there is one, else at the end.
        footer = note.rfind("\n---\n")
        head, tail = (note[:footer], note[footer:]) if footer != -1 else (note, "\n")
        note = f"{head.rstrip()}\n\n{QUOTES_HEADING}\n{tail}"
        match = _QUOTES_SECTION.search(note)
    start = match.end()
    # The section ends at the next heading of level 2, or the footer rule.
    end_match = re.compile(r"^(## |---$)", re.MULTILINE).search(note, start)
    end = end_match.start() if end_match else len(note)
    body = note[start:end].rstrip()
    rest = note[end:]
    new_body = f"{body}\n\n{block}\n\n" if body else f"\n\n{block}\n\n"
    note = note[:start] + new_body + rest
    return _LAST_UPDATED.sub(f"*Last Updated: {today}*", note)


def _new_note(library_root: Path, category: str, title: str, author: str, today: str) -> str:
    template_path = library_root / TEMPLATE
    note = template_path.read_text() if template_path.is_file() else _FALLBACK_TEMPLATE
    note = note.replace("[Book/Article Title]", title.strip(), 1)
    note = note.replace("**Author/Creator:** Name(s)", f"**Author/Creator:** {author.strip()}", 1)
    source_type = _SOURCE_TYPES.get(category.split("/")[0])
    if source_type:
        note = re.sub(r"^\*\*Source Type:\*\* .*$", f"**Source Type:** {source_type}", note,
                      count=1, flags=re.MULTILINE)
    note = note.replace("*Created: YYYY-MM-DD*", f"*Created: {today}*")
    # Drop the template's example quotes: the new quote is the section's only content.
    match = _QUOTES_SECTION.search(note)
    if match:
        end_match = re.compile(r"^(## |---$)", re.MULTILINE).search(note, match.end())
        end = end_match.start() if end_match else len(note)
        note = note[: match.end()] + "\n\n" + note[end:]
    return note


def add_quote(
    library_root: Path,
    source_title: str,
    author: str,
    text: str,
    why: str,
    location: str = "",
    category: str = "books",
    themes: list[str] | None = None,
    links: list[str] | None = None,
    today: str | None = None,
) -> dict:
    """File a quote in `02-literature-notes/<category>/<slug of source_title>.md`.

    Creates the note from the literature-summary template if it does not exist.
    Returns the note's relative path and whether it was created.
    """
    today = today or date.today().isoformat()
    sub = category.strip().strip("/")
    if not sub:
        raise ValueError("category is required, for example 'books' or 'articles'")
    rel = Path(LITERATURE_DIR) / sub / f"{slugify(source_title)}.md"
    full = _safe_join(library_root, str(rel))
    block = format_quote(text, author, source_title, location, why, themes, links)
    created = not full.is_file()
    note = _new_note(library_root, sub, source_title, author, today) if created else full.read_text()
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(insert_quote(note, block, today))
    return {"path": rel.as_posix(), "created": created}
