"""The reading app's side of a book's notes in the knowledge library.

`add_literature_section` adds a note in the reader's own words to the book's
literature note, `02-literature-notes/books/<book-slug>.md`, under a reading
notes section. `source_annotations` reads back everything about one book: the
literature note's quotes and reading notes, and every fleeting-note block that
links to the book's folder in book-library.

A section takes a heading for where it was made, the passage it is about, then
the reader's own words, and ends with the EPUB anchor when there is one:

    ### ch. 3 · 2026-10-31

    > the passage

    The note.

    <!-- anchor: epubcfi(...) -->
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from knowledge_library_mcp.quotes import (
    LITERATURE_DIR,
    _new_note,
    anchor_comment,
    link_from_readme,
)
from knowledge_library_mcp.writer import _safe_join

READING_HEADING = "## 🗒️ Reading Notes"
FLEETING_DIR = "01-fleeting-notes"

_READING_SECTION = re.compile(r"^## .*Reading Notes$", re.MULTILINE)
_QUOTES_SECTION = re.compile(r"^## .*Quotes & Highlights.*$", re.MULTILINE)
_SECTION_END = re.compile(r"^(## |---$)", re.MULTILINE)
_LAST_UPDATED = re.compile(r"^\*Last [Uu]pdated: [^*]*\*$", re.MULTILINE)
_ANCHOR = re.compile(r"^<!-- anchor: (.+?) -->$", re.MULTILINE)


def literature_path(book_slug: str) -> Path:
    return Path(LITERATURE_DIR) / "books" / f"{book_slug}.md"


def format_section(text: str, location: str, today: str, passage: str = "",
                   anchor: str = "") -> str:
    if not text.strip():
        raise ValueError("a reading note needs its text")
    heading = " · ".join(part for part in (location.strip(), today) if part)
    lines = [f"### {heading}", ""]
    if passage.strip():
        lines += [*(f"> {line}" if line else ">" for line in passage.strip().splitlines()), ""]
    lines.append(text.strip())
    if anchor.strip():
        lines += ["", anchor_comment(anchor)]
    return "\n".join(lines)


def _insert_section(note: str, block: str, today: str) -> str:
    """Append `block` to the reading notes section, adding it before the quotes if missing."""
    match = _READING_SECTION.search(note)
    if match is None:
        quotes = _QUOTES_SECTION.search(note)
        footer = note.rfind("\n---\n")
        at = quotes.start() if quotes else (footer + 1 if footer != -1 else len(note))
        note = f"{note[:at].rstrip()}\n\n{READING_HEADING}\n\n{note[at:].lstrip()}"
        match = _READING_SECTION.search(note)
    start = match.end()
    end_match = _SECTION_END.search(note, start)
    end = end_match.start() if end_match else len(note)
    body = note[start:end].rstrip()
    new_body = f"{body}\n\n{block}\n\n" if body else f"\n\n{block}\n\n"
    note = note[:start] + new_body + note[end:]
    return _LAST_UPDATED.sub(f"*Last Updated: {today}*", note)


def add_literature_section(
    library_root: Path,
    book_slug: str,
    title: str,
    author: str,
    text: str,
    location: str = "",
    passage: str = "",
    anchor: str = "",
    today: str | None = None,
) -> dict:
    """Add a reading note to the book's literature note.

    Creates the note if it does not exist and links it from the folder's
    README.md, as `add_quote` does.
    """
    today = today or date.today().isoformat()
    rel = literature_path(book_slug)
    full = _safe_join(library_root, str(rel))
    created = not full.is_file()
    block = format_section(text, location, today, passage, anchor)
    note = _new_note("books", title, author, today) if created else full.read_text()
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(_insert_section(note, block, today))
    result = {"path": rel.as_posix(), "created": created, "linked_from": None}
    readme = full.parent / "README.md"
    if created and readme.is_file():
        readme.write_text(link_from_readme(readme.read_text(), title, full.name, author, today))
        result["linked_from"] = (rel.parent / "README.md").as_posix()
    return result


# ---- Reading back -------------------------------------------------------------


def _section_body(note: str, section: re.Pattern) -> str:
    match = section.search(note)
    if match is None:
        return ""
    end_match = _SECTION_END.search(note, match.end())
    return note[match.end(): end_match.start() if end_match else len(note)]


def _pop_anchor(block: str) -> tuple[str, str]:
    match = _ANCHOR.search(block)
    if match is None:
        return block.strip(), ""
    return (block[: match.start()] + block[match.end():]).strip(), match.group(1).strip()


def _parse_quotes(body: str) -> list[dict]:
    quotes = []
    for chunk in re.split(r"\n(?=> [\"“])", "\n" + body):
        chunk, anchor = _pop_anchor(chunk)
        if not chunk.startswith(">"):
            continue
        quoted = [line[1:].strip() for line in chunk.splitlines() if line.startswith(">")]
        source = next((q for q in quoted if q.startswith("—")), "")
        text = " ".join(q for q in quoted if q and not q.startswith("—")).strip().strip('"“”')
        loc = re.search(r"\*[^*]+\*,\s*(.+)$", source)
        why = re.search(r"^- \*\*Why:\*\*\s*(.+)$", chunk, re.MULTILINE)
        quotes.append({
            "kind": "quote",
            "text": text,
            "location": loc.group(1).strip() if loc else "",
            "why": why.group(1).strip() if why else "",
            "anchor": anchor,
        })
    return quotes


def _parse_sections(body: str) -> list[dict]:
    sections = []
    for chunk in re.split(r"^### ", body, flags=re.MULTILINE)[1:]:
        heading, _, rest = chunk.partition("\n")
        rest, anchor = _pop_anchor(rest)
        lines = rest.splitlines()
        parts = [p.strip() for p in heading.split(" · ")]
        dated = re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[-1]) is not None
        sections.append({
            "kind": "literature",
            "text": "\n".join(ln for ln in lines if not ln.startswith(">")).strip(),
            "passage": "\n".join(ln[1:].strip() for ln in lines if ln.startswith(">")),
            "location": " · ".join(parts[:-1] if dated else parts),
            "date": parts[-1] if dated else "",
            "anchor": anchor,
        })
    return sections


def _fleeting_mentions(library_root: Path, book_slug: str) -> list[dict]:
    """Fleeting-note blocks that link to `book-library/<book_slug>/`."""
    link = f"book-library/{book_slug}/"
    folder = library_root / FLEETING_DIR
    found = []
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        text = path.read_text()
        if link not in text:
            continue
        blocks = re.split(r"^## ", text, flags=re.MULTILINE)
        timed = [b for b in blocks[1:] if re.match(r"\d{2}:\d{2}:\d{2}\n", b)]
        for block in timed or [text]:
            if link not in block:
                continue
            time, _, body = block.partition("\n") if timed else ("", "", block)
            body, anchor = _pop_anchor(body)
            found.append({
                "kind": "fleeting",
                "text": body,
                "path": path.relative_to(library_root).as_posix(),
                "time": time.strip(),
                "anchor": anchor,
            })
    return found


def source_annotations(library_root: Path, book_slug: str) -> dict:
    """Everything the knowledge library holds about one book, as structured data."""
    rel = literature_path(book_slug)
    full = _safe_join(library_root, str(rel))
    note = full.read_text() if full.is_file() else ""
    return {
        "slug": book_slug,
        "literature_note": rel.as_posix() if note else "",
        "quotes": _parse_quotes(_section_body(note, _QUOTES_SECTION)),
        "literature": _parse_sections(_section_body(note, _READING_SECTION)),
        "fleeting": _fleeting_mentions(library_root, book_slug),
    }
