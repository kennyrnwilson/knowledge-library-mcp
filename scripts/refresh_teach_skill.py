"""Refresh the vendored `teach` skill from mattpocock/skills at a given commit.

Usage, from mcp-server/:  uv run python scripts/refresh_teach_skill.py <commit-sha>

Overwrites the upstream files in src/knowledge_library_mcp/teach_skill/. It does
not touch CHAT-PREAMBLE.md or README.md; update the commit in README.md by hand.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

UPSTREAM = "https://raw.githubusercontent.com/mattpocock/skills/{sha}/{path}"
SKILL_PATH = "skills/productivity/teach"
FILES = {
    "SKILL.md": f"{SKILL_PATH}/SKILL.md",
    "MISSION-FORMAT.md": f"{SKILL_PATH}/MISSION-FORMAT.md",
    "RESOURCES-FORMAT.md": f"{SKILL_PATH}/RESOURCES-FORMAT.md",
    "LEARNING-RECORD-FORMAT.md": f"{SKILL_PATH}/LEARNING-RECORD-FORMAT.md",
    "GLOSSARY-FORMAT.md": f"{SKILL_PATH}/GLOSSARY-FORMAT.md",
    "LICENSE": "LICENSE",
}
DEST = Path(__file__).resolve().parents[1] / "src" / "knowledge_library_mcp" / "teach_skill"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    sha = sys.argv[1]
    for name, path in FILES.items():
        with urllib.request.urlopen(UPSTREAM.format(sha=sha, path=path)) as resp:
            (DEST / name).write_bytes(resp.read())
        print(f"updated {name}")
    print(f"Now set the commit in {DEST / 'README.md'} to {sha}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
