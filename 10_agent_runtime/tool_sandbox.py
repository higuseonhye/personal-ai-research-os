"""
Tool-using agent runtime (restricted code execution + stub browser/fetch tools).

Production deployments should swap subprocess executor for stronger isolation (containers).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ToolResult:
    tool: str
    ok: bool
    payload: dict[str, Any]
    stderr: str = ""


ALLOWED_MODULES = frozenset({"math", "json", "re", "datetime", "statistics", "hashlib"})
BANNED_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
    }
)


def _validate_ast(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise ValueError(f"Name not allowed in snippet: {node.id}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_NAMES:
            raise ValueError(f"Call not allowed: {node.func.id}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = getattr(node, "module", None)
            if isinstance(node, ast.ImportFrom):
                if mod not in ALLOWED_MODULES:
                    raise ValueError(f"Import not allowed: {mod}")
            else:
                for alias in node.names:
                    if alias.name.split(".")[0] not in ALLOWED_MODULES:
                        raise ValueError(f"Import not allowed: {alias.name}")


def execute_python_snippet(code: str, *, timeout_sec: float = 8.0, cwd: Path | None = None) -> ToolResult:
    """
    Run Python in a subprocess with stripped imports validated by AST.
    No network / filesystem beyond temp semantics unless you harden further.

    Env:
      PA_TOOL_MAX_CODE_BYTES — max UTF-8 length (default 65536).
      PA_TOOL_WORKSPACE_ROOT — if set, subprocess cwd is pinned under this directory.
    """
    max_bytes = int(os.environ.get("PA_TOOL_MAX_CODE_BYTES", "65536"))
    code = textwrap.dedent(code).strip()
    if len(code.encode("utf-8")) > max_bytes:
        return ToolResult(
            tool="python_snippet",
            ok=False,
            payload={"error": f"code exceeds PA_TOOL_MAX_CODE_BYTES ({max_bytes})"},
        )
    try:
        _validate_ast(code)
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            tool="python_snippet",
            ok=False,
            payload={"error": str(e)},
        )

    effective_cwd: Path | None = None
    ws = os.environ.get("PA_TOOL_WORKSPACE_ROOT", "").strip()
    if ws:
        root = Path(ws).expanduser().resolve()
        if cwd:
            cand = Path(cwd).expanduser().resolve()
            try:
                cand.relative_to(root)
                effective_cwd = cand
            except ValueError:
                effective_cwd = root
        else:
            effective_cwd = root
    elif cwd:
        effective_cwd = Path(cwd).expanduser().resolve()

    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        cwd=str(effective_cwd) if effective_cwd else None,
    )
    ok = proc.returncode == 0
    return ToolResult(
        tool="python_snippet",
        ok=ok,
        payload={"stdout": proc.stdout[-8000:], "returncode": proc.returncode},
        stderr=proc.stderr[-4000:],
    )


def browser_stub_navigate(url: str, *, max_chars: int = 800) -> ToolResult:
    """Placeholder until Playwright/Selenium integration + enterprise proxy policies."""
    return ToolResult(
        tool="browser_navigate",
        ok=False,
        payload={
            "error": "browser_tool_not_configured",
            "hint": "Wire Playwright with allowlisted domains and audit logging.",
            "url": url[:500],
            "preview_chars": max_chars,
        },
    )


def http_fetch_stub(url: str) -> ToolResult:
    """Placeholder — enable httpx/aiohttp with SSRF controls in production."""
    return ToolResult(
        tool="http_fetch",
        ok=False,
        payload={"error": "http_fetch_disabled_by_default", "url": url[:500]},
    )


ToolFn = Callable[..., ToolResult]

TOOL_REGISTRY: dict[str, ToolFn] = {
    "python_snippet": execute_python_snippet,
    "browser_navigate": browser_stub_navigate,
    "http_fetch": http_fetch_stub,
}


def dispatch_tool(name: str, **kwargs: Any) -> ToolResult:
    if name == "python_snippet":
        code = str(kwargs.get("code", "") or "")
        return execute_python_snippet(code, cwd=kwargs.get("cwd"))
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        return ToolResult(tool=name, ok=False, payload={"error": "unknown_tool"})
    return fn(**kwargs)


def tools_schema() -> list[dict[str, Any]]:
    return [
        {"name": "python_snippet", "args": ["code"], "risk": "medium"},
        {"name": "browser_navigate", "args": ["url"], "risk": "high"},
        {"name": "http_fetch", "args": ["url"], "risk": "high"},
    ]
