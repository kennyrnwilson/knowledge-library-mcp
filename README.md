# knowledge-library-mcp

MCP server exposing the knowledge-library (notes, guidance, projects, search, plus explicit-save write tools) to Claude clients.

## Run locally

```bash
cd mcp-server
uv sync --extra dev
uv run python -m knowledge_library_mcp --selftest
```

## Run tests

```bash
uv run pytest
```

## Configuration

The server resolves the library root by:
1. `KNOWLEDGE_LIBRARY_ROOT` environment variable, if set.
2. The parent directory of the `mcp-server/` directory (the default in production).

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

Write tools (`create_note`, `update_note`, `append_fleeting`, `write_teach_file`, `edit_teach_file`) only touch disk. They never commit. The `save_changes` tool stages, commits, and pushes. The LLM must only call `save_changes` when the user explicitly approves ("save it", "commit that", "looks good").

## Staying in step with `main`

The server's clone is only pulled when it is installed, so on its own it falls
behind every push made elsewhere. Two things keep it current, and both act only
when `main` is checked out:

- **Before each tool call**, `refresh` runs `git pull --ff-only origin main`, at
  most once every 30 seconds, with a 15-second timeout. A failed pull is not an
  error: the call goes ahead on what is on disk.
- **`save_changes`** commits, fetches, rebases onto `origin/main`, then pushes. A
  conflict aborts the rebase and leaves the commit local, with an error that
  says so. A commit stranded by an earlier failed push goes out with the next
  `save_changes`, even when there is nothing new to commit.

## Deployment

This directory is the source of truth. On every push to `main` that touches
`mcp-server/`, `.github/workflows/sync-to-public.yml` mirrors it into the public
repo `kennyrnwilson/knowledge-library-mcp`. A push to that public repo runs its
`deploy-vm.yml` on the Mac Mini self-hosted runner, which pulls, runs `uv sync`,
and restarts the `knowledge-library-mcp` systemd unit inside the ingress VM
(port 5103, behind `gateway.kennyrnwilson.com/mcp/knowledge`).

The knowledge content itself never leaves the private repo — only this
`mcp-server/` subtree is mirrored.
