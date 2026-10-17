"""Teaching workspaces: the `teach` skill served over MCP.

A project's teaching workspace is `05-projects/<project>/teach/`, laid out as
Matt Pocock's `teach` skill expects (see `teach_skill/`). These functions let a
chat that has no skills of its own run that skill: `teach_start` hands over the
instructions and the workspace state, and the write functions store what the
chat produces. Like the rest of `writer.py`, they only touch disk; `save_changes`
is still the only path to git.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

_PROJECTS = "05-projects"
_WORKSPACE = "teach"
_SKILL_DIR = Path(__file__).parent / "teach_skill"

# The preamble comes first so its overrides frame everything after it.
_INSTRUCTION_FILES = (
    "CHAT-PREAMBLE.md",
    "SKILL.md",
    "MISSION-FORMAT.md",
    "RESOURCES-FORMAT.md",
    "LEARNING-RECORD-FORMAT.md",
    "GLOSSARY-FORMAT.md",
)

_STATE_FILES = ("MISSION.md", "RESOURCES.md", "NOTES.md")
_SUBDIRS = ("lessons", "reference", "learning-records", "assets")

# .json is left out on purpose: the portal's copy step does not publish it.
_ALLOWED_SUFFIXES = {".html", ".css", ".js", ".svg", ".md"}

# Assets larger than this are listed by path only, so teach_start stays small.
_ASSET_INLINE_LIMIT = 40_000

_PROJECT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NUMBERED_RE = re.compile(r"^(\d{4})-")


class TeachError(ValueError):
    """A teaching-workspace request that cannot be carried out."""


def load_instructions() -> str:
    """The chat preamble followed by the vendored skill files, as one document."""
    parts = []
    for name in _INSTRUCTION_FILES:
        parts.append(f"<!-- file: {name} -->\n{(_SKILL_DIR / name).read_text()}")
    return "\n\n".join(parts)


def _project_dir(library_root: Path, project: str) -> Path:
    if not _PROJECT_RE.match(project):
        raise TeachError(f"invalid project name: {project!r}; expected a kebab-case folder name")
    path = library_root / _PROJECTS / project
    if not (path / "README.md").is_file():
        raise TeachError(f"no such project: {_PROJECTS}/{project}/README.md does not exist")
    return path


def _workspace(library_root: Path, project: str) -> Path:
    return _project_dir(library_root, project) / _WORKSPACE


def _rel(library_root: Path, path: Path) -> str:
    return path.relative_to(library_root).as_posix()


def published_url(relative_path: str) -> str:
    """The portal URL path for a library file, following the portal's slug rules.

    Other files are copied as-is, so `NN-` prefixes go from directories only. A
    `.md` file becomes an Astro page: lower-cased, `NN-` stripped from every
    segment, `README`/`index` collapsed onto the directory, trailing slash.
    """
    parts = relative_path.split("/")
    dirs = [re.sub(r"^\d+-", "", p) for p in parts[:-1]]
    name = parts[-1]
    if not name.endswith(".md"):
        return "/knowledge/" + "/".join([*dirs, name])
    stem = re.sub(r"^\d+-", "", name[:-3])
    segments = dirs if stem.lower() in ("readme", "index") else [*dirs, stem]
    return "/knowledge/" + "/".join(segments).lower() + "/"


def _workspace_file(library_root: Path, project: str, path: str) -> Path:
    """Resolve `path` inside the workspace, refusing anything the skill would not write."""
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise TeachError(f"path must be relative to the workspace, without '..': {path!r}")
    if rel.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise TeachError(
            f"file type not allowed: {rel.suffix or '(none)'}; expected one of "
            f"{sorted(_ALLOWED_SUFFIXES)}"
        )
    top = rel.parts[0]
    if len(rel.parts) == 1:
        if top not in _STATE_FILES:
            raise TeachError(f"top-level file must be one of {list(_STATE_FILES)}: {path!r}")
    elif top not in _SUBDIRS:
        raise TeachError(f"path must start with one of {list(_SUBDIRS)}: {path!r}")
    workspace = _workspace(library_root, project).resolve()
    full = (workspace / rel).resolve()
    if not full.is_relative_to(workspace):
        raise TeachError(f"path escapes the workspace: {path!r}")
    return full


class _TextExtractor(HTMLParser):
    """Collects readable text and the <title>, skipping scripts and styles."""

    _SKIP = {"script", "style", "noscript", "template"}
    _BLOCK = {"p", "div", "section", "article", "li", "tr", "br", "hr", "pre", "blockquote",
              "h1", "h2", "h3", "h4", "h5", "h6", "button", "summary", "figcaption", "td", "th"}

    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self.title = ""
        self.h1 = ""
        self._skip_depth = 0
        self._in_title = False
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        if tag in self._BLOCK:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        if tag in self._BLOCK:
            self.chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
            return
        if self._in_h1:
            self.h1 += data
        self.chunks.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self.chunks).splitlines())
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _parse_html(html: str) -> _TextExtractor:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser


def list_lessons(library_root: Path, project: str) -> list[dict]:
    """The numbered lessons in a project's workspace, oldest first."""
    lessons_dir = _workspace(library_root, project) / "lessons"
    if not lessons_dir.is_dir():
        return []
    out = []
    for f in sorted(lessons_dir.glob("*.html")):
        m = _NUMBERED_RE.match(f.name)
        parsed = _parse_html(f.read_text())
        rel = _rel(library_root, f)
        out.append({
            "number": int(m.group(1)) if m else None,
            "title": (parsed.title or parsed.h1 or f.stem).strip(),
            "path": rel,
            "url": published_url(rel),
        })
    return out


def get_lesson(library_root: Path, relative_path: str) -> str:
    """The readable text of a lesson or reference page, without markup, scripts or styles."""
    full = (library_root / relative_path).resolve()
    root = library_root.resolve()
    parts = Path(relative_path).parts
    if (
        ".." in parts
        or not full.is_relative_to(root)
        or full.suffix != ".html"
        or len(parts) < 5
        or parts[0] != _PROJECTS
        or parts[2] != _WORKSPACE
    ):
        raise TeachError(
            f"not a workspace page: {relative_path!r}; expected "
            f"{_PROJECTS}/<project>/{_WORKSPACE}/<lessons|reference>/<file>.html"
        )
    if not full.is_file():
        raise TeachError(f"lesson not found: {relative_path}")
    parsed = _parse_html(full.read_text())
    title = (parsed.title or parsed.h1).strip()
    body = parsed.text()
    return f"# {title}\n\n{body}" if title else body


def teach_start(library_root: Path, project: str) -> dict:
    """The skill's instructions plus everything the workspace holds today.

    Lessons and reference pages are listed, not inlined; the chat reads one with
    `get_lesson` only when it needs it. State files, learning records and small
    assets are inlined, because the skill reads them before every lesson.
    """
    workspace = _workspace(library_root, project)

    def read(path: Path) -> str | None:
        return path.read_text() if path.is_file() else None

    records = []
    records_dir = workspace / "learning-records"
    if records_dir.is_dir():
        for f in sorted(records_dir.glob("*.md")):
            records.append({"path": f"learning-records/{f.name}", "content": f.read_text()})

    assets = []
    assets_dir = workspace / "assets"
    if assets_dir.is_dir():
        for f in sorted(p for p in assets_dir.rglob("*") if p.is_file()):
            entry = {"path": f.relative_to(workspace).as_posix()}
            if f.stat().st_size <= _ASSET_INLINE_LIMIT and f.suffix.lower() in _ALLOWED_SUFFIXES:
                entry["content"] = f.read_text()
            assets.append(entry)

    reference = []
    reference_dir = workspace / "reference"
    if reference_dir.is_dir():
        for f in sorted(reference_dir.glob("*.html")):
            rel = _rel(library_root, f)
            reference.append({"path": rel, "url": published_url(rel)})

    return {
        "instructions": load_instructions(),
        "workspace": _rel(library_root, workspace),
        "exists": workspace.is_dir(),
        "project_readme": (workspace.parent / "README.md").read_text(),
        "state": {name: read(workspace / name) for name in _STATE_FILES},
        "learning_records": records,
        "lessons": list_lessons(library_root, project),
        "reference": reference,
        "assets": assets,
    }


def write_teach_file(library_root: Path, project: str, path: str, content: str) -> dict:
    """Create or replace one workspace file. Returns its library path and published URL."""
    full = _workspace_file(library_root, project, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    rel = _rel(library_root, full)
    return {"path": rel, "url": published_url(rel)}


def edit_teach_file(library_root: Path, project: str, path: str, old: str, new: str) -> dict:
    """Replace one exact, unique occurrence of `old` in an existing workspace file."""
    full = _workspace_file(library_root, project, path)
    if not full.is_file():
        raise TeachError(f"cannot edit; file does not exist: {path}")
    text = full.read_text()
    count = text.count(old) if old else 0
    if count != 1:
        raise TeachError(f"`old` must occur exactly once in {path}; found {count}")
    full.write_text(text.replace(old, new, 1))
    rel = _rel(library_root, full)
    return {"path": rel, "url": published_url(rel)}
