"""Git operations for the knowledge-library: status + explicit save."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SaveResult:
    committed: bool
    pushed: bool
    commit_sha: str = ""
    message: str = ""
    pending: list[dict] = field(default_factory=list)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def list_pending_changes(library_root: Path) -> list[dict]:
    """Return parsed `git status --porcelain` for the library."""
    proc = _run(["git", "status", "--porcelain", "-z"], library_root)
    if proc.returncode != 0:
        raise RuntimeError(f"git status failed: {proc.stderr.strip()}")
    out: list[dict] = []
    chunk = proc.stdout.split("\x00")
    for entry in chunk:
        if not entry:
            continue
        if len(entry) < 4:
            continue
        status = entry[:2]
        path = entry[3:]
        out.append({"status": status, "path": path})
    return out


def _autogenerate_message(pending: list[dict]) -> str:
    if not pending:
        return "save: no changes"
    paths = [p["path"] for p in pending]
    if len(paths) == 1:
        return f"save: {paths[0]}"
    head = paths[:3]
    extra = len(paths) - len(head)
    suffix = f" (+{extra} more)" if extra > 0 else ""
    return f"save: {', '.join(head)}{suffix}"


def save_changes(library_root: Path, message: str | None = None) -> SaveResult:
    """Stage all changes, commit, push origin main. No-op if working tree clean."""
    pending = list_pending_changes(library_root)
    if not pending:
        return SaveResult(committed=False, pushed=False, pending=[])

    add = _run(["git", "add", "-A"], library_root)
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr.strip()}")

    commit_msg = message or _autogenerate_message(pending)
    commit = _run(["git", "commit", "-m", commit_msg], library_root)
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")

    sha_proc = _run(["git", "rev-parse", "--short", "HEAD"], library_root)
    sha = sha_proc.stdout.strip()

    push = _run(["git", "push", "origin", "main"], library_root)
    if push.returncode != 0:
        raise RuntimeError(
            f"git push failed (commit {sha} stays local): {push.stderr.strip()}"
        )
    return SaveResult(
        committed=True, pushed=True, commit_sha=sha, message=commit_msg, pending=pending
    )
