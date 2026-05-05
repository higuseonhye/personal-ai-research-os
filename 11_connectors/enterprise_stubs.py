"""
Enterprise connector stubs (Slack / Jira / Notion). Replace bodies with OAuth + API clients.

Security: never ship tokens in-repo; load from env / vault.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def fetch_slack_export_stub(path: Path | None = None) -> list[dict[str, Any]]:
    """
    Load a Slack export directory JSON if present; otherwise return [] with hints.
    """
    root = path or Path(os.environ.get("SLACK_EXPORT_PATH", ""))
    if not root or not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in root.rglob("*.json"):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                out.extend([x for x in raw if isinstance(x, dict)])
            elif isinstance(raw, dict):
                out.append(raw)
        except json.JSONDecodeError:
            continue
    return out[:5000]


def fetch_jira_issues_stub(jql: str = "") -> list[dict[str, Any]]:
    token = os.environ.get("JIRA_API_TOKEN", "")
    base = os.environ.get("JIRA_BASE_URL", "")
    if not token or not base:
        return []
    try:
        import requests  # type: ignore[import-untyped]
    except ImportError:
        return []
    r = requests.get(
        f"{base.rstrip('/')}/rest/api/3/search",
        params={"jql": jql or "order by created DESC", "maxResults": 50},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code != 200:
        return []
    data = r.json()
    return list(data.get("issues") or [])


def fetch_notion_pages_stub(database_id: str = "") -> list[dict[str, Any]]:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        return []
    try:
        import requests  # type: ignore[import-untyped]
    except ImportError:
        return []
    url = "https://api.notion.com/v1/search" if not database_id else f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    r = requests.post(url, json={}, headers=headers, timeout=30) if not database_id else requests.post(
        url, json={"page_size": 50}, headers=headers, timeout=30
    )
    if r.status_code != 200:
        return []
    data = r.json()
    return list(data.get("results") or [])
