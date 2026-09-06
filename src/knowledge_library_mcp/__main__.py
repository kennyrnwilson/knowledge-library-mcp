"""Entry point: `python -m knowledge_library_mcp` (stdio server) or `--selftest`."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from typing import Any

from knowledge_library_mcp.server import build_server


def _coerce(call_tool_result: Any) -> Any:
    if isinstance(call_tool_result, tuple) and len(call_tool_result) == 2:
        content, structured = call_tool_result
        if structured is not None:
            if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
                return structured["result"]
            return structured
        return _from_content(content)
    if isinstance(call_tool_result, list):
        return _from_content(call_tool_result)
    return call_tool_result


def _from_content(content: Any) -> Any:
    for item in content or []:
        if getattr(item, "type", None) == "text":
            try:
                return json.loads(item.text)
            except (json.JSONDecodeError, TypeError):
                return item.text
    return None


def _selftest() -> int:
    server = build_server()

    async def run() -> int:
        try:
            areas = _coerce(await server.call_tool("list_areas", {}))
            if len(areas) != 6:
                print(f"selftest FAIL: list_areas returned {len(areas)} areas, expected 6", file=sys.stderr)
                return 1
            await server.call_tool("search_notes", {"query": "the"})
            await server.call_tool("list_permanent_notes", {"area": areas[0]})
            await server.call_tool("list_projects", {})
            print(f"selftest OK: {len(areas)} areas; first area={areas[0]!r}")
            return 0
        except Exception:
            print("selftest FAIL:", file=sys.stderr)
            traceback.print_exc()
            return 1

    return asyncio.run(run())


def main() -> int:
    parser = argparse.ArgumentParser(prog="knowledge-library-mcp")
    parser.add_argument("--selftest", action="store_true",
                        help="Instantiate the server, call read tools, exit 0/1.")
    parser.add_argument("--transport", default="stdio",
                        choices=["stdio", "streamable-http"],
                        help="Transport to use (default: stdio).")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind when using streamable-http transport (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=5103,
                        help="Port to bind when using streamable-http transport (default: 5103).")
    args = parser.parse_args()

    if args.selftest:
        return _selftest()

    server = build_server(host=args.host, port=args.port)
    if args.transport == "streamable-http":
        server.run(transport="streamable-http")
    else:
        server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
