"""Shared pytest fixtures for knowledge-library-mcp tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def fixture_library() -> Path:
    """Path to the in-tree mock library."""
    return Path(__file__).parent / "fixtures" / "library"


@pytest.fixture
def temp_library(tmp_path: Path, fixture_library: Path) -> Path:
    """A throwaway copy of the fixture library that tests can mutate."""
    dst = tmp_path / "library"
    shutil.copytree(fixture_library, dst)
    return dst


@pytest.fixture
def temp_git_library(temp_library: Path) -> Path:
    """temp_library with a git repo and a local bare-repo origin so save_changes can push."""
    bare = temp_library.parent / "origin.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--initial-branch=main", str(temp_library)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(temp_library), "remote", "add", "origin", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(temp_library), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(temp_library), "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(temp_library), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(temp_library), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(temp_library), "push", "-u", "origin", "main"], check=True, capture_output=True)
    return temp_library
