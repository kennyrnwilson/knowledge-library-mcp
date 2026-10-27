"""add_quote: file a quote in its source's literature note, in the four-part shape.

The shape is the quotes section of knowledge-library's `.templates/literature-summary.md`:

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
QUOTES_HEADING = "## 💬 Quotes & Highlights"
NOTES_HEADING = "## Notes"

# A new note holds only what a quote fills in. The full literature-summary
# template would leave its placeholders (status, rating, takeaways) unfilled.
_NEW_NOTE = """# {title}

← [Back to Parent](./README.md)

**Author/Creator:** {author}
**Source Type:** {source_type}

## 💬 Quotes & Highlights

---

**Tags:** #literature

*Created: {today}*
*Last Updated: {today}*
"""

_SOURCE_TYPES = {
    "books": "Book",
    "articles": "Article",
    "courses": "Course",
}

_QUOTES_SECTION = re.compile(r"^## .*Quotes & Highlights.*$", re.MULTILINE)
_LAST_UPDATED = re.compile(r"^\*Last [Uu]pdated: [^*]*\*$", re.MULTILINE)
_SECTION_END = re.compile(r"^(## |---$)", re.MULTILINE)
# A "why" such as "<your own sentence>": a template the user sent back unfilled.
_PLACEHOLDER = re.compile(r"<[^>]*>")


def format_quote(
    text: str,
    author: str,
    title: str,
    location: str,
    why: str,
    themes: list[str] | None = None,
    links: list[str] | None = None,
    said_by: str = "",
) -> str:
    """Return one quote in the four-part shape, without surrounding blank lines.

    `said_by` names the speaker when the source quotes someone else: the source
    line then reads "— Speaker, quoted in Author, *Title*".
    """
    text = text.strip().strip('"“”')
    if not text:
        raise ValueError("a quote needs its text")
    if not why.strip():
        raise ValueError("a quote needs a 'why': one line on why it mattered")
    if _PLACEHOLDER.search(why):
        raise ValueError("the 'why' is a placeholder; ask the user why the quote matters")
    source = f"— {author.strip()}, *{title.strip()}*"
    if said_by.strip():
        source = f"— {said_by.strip()}, quoted in {author.strip()}, *{title.strip()}*"
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


def _new_note(category: str, title: str, author: str, today: str) -> str:
    source_type = _SOURCE_TYPES.get(category.split("/")[0], "Book | Article | Course")
    return _NEW_NOTE.format(title=title.strip(), author=author.strip(),
                            source_type=source_type, today=today)


def link_from_readme(readme: str, title: str, filename: str, author: str, today: str) -> str:
    """Add a link to a new note under the README's notes heading, adding one if missing."""
    line = f"- [{title.strip()}](./{filename}) ({author.strip()})"
    match = re.search(rf"^{re.escape(NOTES_HEADING)}$", readme, re.MULTILINE)
    if match is None:
        footer = readme.rfind("\n---\n")
        head, tail = (readme[:footer], readme[footer:]) if footer != -1 else (readme, "\n")
        readme = f"{head.rstrip()}\n\n{NOTES_HEADING}\n{tail}"
        match = re.search(rf"^{re.escape(NOTES_HEADING)}$", readme, re.MULTILINE)
    start = match.end()
    end_match = _SECTION_END.search(readme, start)
    end = end_match.start() if end_match else len(readme)
    body = readme[start:end].rstrip()
    new_body = f"{body}\n{line}\n\n" if body else f"\n\n{line}\n\n"
    readme = readme[:start] + new_body + readme[end:]
    return _LAST_UPDATED.sub(f"*Last Updated: {today}*", readme)


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
    said_by: str = "",
    today: str | None = None,
) -> dict:
    """File a quote in `02-literature-notes/<category>/<slug of source_title>.md`.

    Creates the note if it does not exist, and links it from the folder's
    README.md. Returns the note's relative path, whether it was created, and the
    README it was linked from, if any.
    """
    today = today or date.today().isoformat()
    sub = category.strip().strip("/")
    if not sub:
        raise ValueError("category is required, for example 'books' or 'articles'")
    rel = Path(LITERATURE_DIR) / sub / f"{slugify(source_title)}.md"
    full = _safe_join(library_root, str(rel))
    block = format_quote(text, author, source_title, location, why, themes, links, said_by)
    created = not full.is_file()
    note = _new_note(sub, source_title, author, today) if created else full.read_text()
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(insert_quote(note, block, today))
    result = {"path": rel.as_posix(), "created": created, "linked_from": None}
    readme = full.parent / "README.md"
    if created and readme.is_file():
        readme.write_text(link_from_readme(readme.read_text(), source_title, full.name,
                                           author, today))
        result["linked_from"] = (rel.parent / "README.md").as_posix()
    return result
