"""Git operations for the knowledge-library: status + explicit save."""

from __future__ import annotations

import subprocess
import time
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


# Seconds between refreshes. Every tool call refreshes, so this keeps a burst of
# calls in one chat turn to a single fetch.
REFRESH_INTERVAL = 30.0
# A slow network must not hang a read; past this, the read uses what is on disk.
REFRESH_TIMEOUT = 15.0
_last_refresh: dict[Path, float] = {}


def _on_main(library_root: Path) -> bool:
    """True when the library is a git clone with `main` checked out."""
    proc = _run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], library_root)
    return proc.returncode == 0 and proc.stdout.strip() == "main"


def refresh(library_root: Path) -> bool:
    """Fast-forward the library to origin/main, at most once per REFRESH_INTERVAL.

    Best effort. knowledge-library's sync-to-vm workflow pulls the clone on each
    push, but only then, and its ff-only pull stalls once a local commit is left
    unpushed. A failed pull here (offline, diverged, or local edits in the way)
    is not an error; the read goes ahead on what is on disk, and save_changes
    reconciles before it pushes. Returns True if it pulled.
    """
    now = time.monotonic()
    key = library_root.resolve()
    if now - _last_refresh.get(key, float("-inf")) < REFRESH_INTERVAL:
        return False
    _last_refresh[key] = now
    if not _on_main(library_root):
        return False
    try:
        pull = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"], cwd=str(library_root),
            capture_output=True, text=True, check=False, timeout=REFRESH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False
    return pull.returncode == 0


def _ahead_of_origin(library_root: Path) -> int:
    proc = _run(["git", "rev-list", "--count", "origin/main..HEAD"], library_root)
    return int(proc.stdout.strip()) if proc.returncode == 0 else 0


def _in_paths(path: str, paths: list[str]) -> bool:
    """True if a pending path is one of `paths`, under one, or an untracked folder holding one."""
    return any(
        path == p or path.startswith(p.rstrip("/") + "/") or (path.endswith("/") and p.startswith(path))
        for p in paths
    )


def save_changes(
    library_root: Path, message: str | None = None, paths: list[str] | None = None
) -> SaveResult:
    """Stage changes, commit, rebase onto origin/main, push.

    With `paths`, only changes under those paths are committed; other pending
    changes stay uncommitted on disk. Also pushes commits left local by an
    earlier failed push, so one failure doesn't strand them. No-op only when
    there is nothing to commit or push.
    """
    if not _on_main(library_root):
        raise RuntimeError("save_changes only runs with `main` checked out; nothing was committed")
    pending = list_pending_changes(library_root)
    if paths:
        pending = [p for p in pending if _in_paths(p["path"], paths)]
    scope = ["--", *paths] if paths else []
    commit_msg = ""
    if pending:
        add = _run(["git", "add", "-A", *scope], library_root)
        if add.returncode != 0:
            raise RuntimeError(f"git add failed: {add.stderr.strip()}")

        commit_msg = message or _autogenerate_message(pending)
        commit = _run(["git", "commit", "-m", commit_msg, *scope], library_root)
        if commit.returncode != 0:
            raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")

    fetch = _run(["git", "fetch", "origin", "main"], library_root)
    if fetch.returncode != 0:
        raise RuntimeError(
            f"git fetch failed (nothing pushed; commits stay local): {fetch.stderr.strip()}"
        )
    if not pending and _ahead_of_origin(library_root) == 0:
        return SaveResult(committed=False, pushed=False, pending=[])

    rebase = _run(["git", "rebase", "--autostash", "origin/main"], library_root)
    if rebase.returncode != 0:
        _run(["git", "rebase", "--abort"], library_root)
        raise RuntimeError(
            "these changes conflict with newer commits on origin/main; nothing was "
            "pushed and the commits stay local. Resolve the conflict in the "
            f"server's clone, then save again. git said: {rebase.stdout.strip()} "
            f"{rebase.stderr.strip()}".strip()
        )

    sha = _run(["git", "rev-parse", "--short", "HEAD"], library_root).stdout.strip()

    push = _run(["git", "push", "origin", "main"], library_root)
    if push.returncode != 0:
        raise RuntimeError(
            f"git push failed (commit {sha} stays local): {push.stderr.strip()}"
        )
    return SaveResult(
        committed=bool(pending), pushed=True, commit_sha=sha, message=commit_msg,
        pending=pending,
    )
