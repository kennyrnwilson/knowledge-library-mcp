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

## Explicit-save model

Write tools (`create_note`, `update_note`, `append_fleeting`) only touch disk. They never commit. The `save_changes` tool stages, commits, and pushes. The LLM must only call `save_changes` when the user explicitly approves ("save it", "commit that", "looks good").

## Deployment

This directory is the source of truth. On every push to `main` that touches
`mcp-server/`, `.github/workflows/sync-to-public.yml` mirrors it into the public
repo `kennyrnwilson/knowledge-library-mcp`. A push to that public repo runs its
`deploy-vm.yml` on the Mac Mini self-hosted runner, which pulls, runs `uv sync`,
and restarts the `knowledge-library-mcp` systemd unit inside the ingress VM
(port 5103, behind `gateway.kennyrnwilson.com/mcp/knowledge`).

The knowledge content itself never leaves the private repo — only this
`mcp-server/` subtree is mirrored.
