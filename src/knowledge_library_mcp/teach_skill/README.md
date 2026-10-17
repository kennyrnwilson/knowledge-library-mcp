# teach_skill

← [Back to Parent](../../../README.md)

A vendored copy of Matt Pocock's `teach` skill, which the `teach_start` tool
returns so that a chat with no skills of its own can teach the way `/teach` does
in Claude Code.

- **Upstream:** [`mattpocock/skills`](https://github.com/mattpocock/skills),
  `skills/productivity/teach/`
- **Commit:** `49dd158d1076134a641b33efb035946536778336` (2026-10-09)
- **Licence:** MIT, see [`LICENSE`](./LICENSE)

The upstream files (`SKILL.md` and the `*-FORMAT.md` files) are copied without
change. [`CHAT-PREAMBLE.md`](./CHAT-PREAMBLE.md) is ours: it adapts the skill to
a workspace reached through MCP tools instead of a working directory.

To refresh the upstream files, run from the repository root:

```bash
uv run python scripts/refresh_teach_skill.py <commit-sha>
```

Then update the commit above, run the tests, and read the upstream diff for
changes that the preamble must follow.
