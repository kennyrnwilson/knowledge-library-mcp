# knowledge-library-mcp

MCP server exposing the knowledge-library (notes, guidance, projects, search, plus explicit-save write tools) to Claude clients.

## Run locally

```bash
uv sync --extra dev
KNOWLEDGE_LIBRARY_ROOT=~/code/knowledge-library uv run python -m knowledge_library_mcp --selftest
```

## Run tests

```bash
uv run pytest
uv run ruff check src tests scripts
```

The tests need `ripgrep` (`rg`) on `PATH`. They run against the fixture library in
`tests/fixtures/library/`, not against real notes.

## Configuration

The server resolves the library root by:
1. `KNOWLEDGE_LIBRARY_ROOT` environment variable, if set.
2. Otherwise, the directory three levels above `server.py`. That default dates
   from when this code lived in `knowledge-library/mcp-server/`; outside that
   layout, set the variable. The ingress VM sets it to its clone,
   `/opt/knowledge-library`.

## Tools exposed

See `src/knowledge_library_mcp/server.py`. Spec: `kennyrnwilson/knowledge-library` → `docs/superpowers/specs/2026-05-08-mcp-knowledge-platform-design.md` § 6.2.

## Teaching tools

`teach_start`, `list_lessons`, `get_lesson`, `write_teach_file` and `edit_teach_file`
let a chat with no skills of its own (claude.ai, for example) run Matt Pocock's
`teach` skill. The workspace is `05-projects/<project>/teach/`; the project must
already have a `README.md`. `teach_start` returns the skill's instructions, from
the vendored copy in [`src/knowledge_library_mcp/teach_skill/`](./src/knowledge_library_mcp/teach_skill/README.md),
plus the workspace's state. The write tools accept `.html`, `.css`, `.js`, `.svg`
and `.md` files inside the workspace only, and like the other write tools they
never commit.

## Explicit-save model

Write tools (`create_note`, `update_note`, `append_fleeting`, `add_quote`, `write_teach_file`, `edit_teach_file`) only touch disk. They never commit. The `save_changes` tool stages, commits, and pushes. The LLM must only call `save_changes` when the user explicitly approves ("save it", "commit that", "looks good").

## Staying in step with `main`

knowledge-library's `sync-to-vm.yml` fast-forwards the server's clone on every
push to `main`. That isn't enough on its own: it runs only on a push, and its
`--ff-only` pull stops working once the clone holds a commit that an earlier
`save_changes` failed to push. Two things here cover the gaps, and both act only
when `main` is checked out:

- **Before each tool call**, `refresh` runs `git pull --ff-only origin main`, at
  most once every 30 seconds, with a 15-second timeout. A failed pull is not an
  error: the call goes ahead on what is on disk.
- **`save_changes`** commits, fetches, rebases onto `origin/main`, then pushes. A
  conflict aborts the rebase and leaves the commit local, with an error that
  says so. A commit stranded by an earlier failed push goes out with the next
  `save_changes`, even when there is nothing new to commit.

## Deployment

This repo is the source of truth for the server. (It used to be a mirror of
`knowledge-library/mcp-server/`; that subtree and its sync were removed on
2026-10-17.) The knowledge content stays in the private `knowledge-library` repo.

`.github/workflows/deploy-vm.yml` runs lint, the tests and the selftest on every
pull request and push. On a push to `main`, it then runs personal-portal's
`deploy/ingress-vm/knowledge-library-mcp.sh install` inside the ingress VM, on
the Mac Mini's self-hosted runner. That installs dependencies pinned by `uv.lock`
and restarts the `knowledge-library-mcp` systemd unit (port 5103, behind
`gateway.kennyrnwilson.com/mcp/knowledge`).
