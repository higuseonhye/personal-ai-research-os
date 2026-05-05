"""
Normalize connector payloads into RAG chunks with ACL metadata (`acl_principals`).

Downstream indexing should pass `metadata` from these dicts into `EmbeddingStore.add`.
"""

from __future__ import annotations

from typing import Any


def slack_message_to_chunk(
    row: dict[str, Any],
    *,
    channel_id: str,
    channel_member_principal_ids: list[str] | None = None,
) -> dict[str, Any]:
    text = str(row.get("text") or row.get("message") or "").strip()
    ts = row.get("ts") or row.get("event_ts")
    principals = list(channel_member_principal_ids or row.get("member_principal_ids") or [])
    if not principals:
        principals = [f"slack:channel:{channel_id}"]
    return {
        "text": text,
        "metadata": {
            "source": "slack",
            "channel_id": channel_id,
            "ts": ts,
            "acl_principals": principals,
        },
    }


def jira_issue_to_chunk(issue: dict[str, Any], *, viewer_principals: list[str]) -> dict[str, Any]:
    fields = issue.get("fields") or issue
    summary = str(fields.get("summary") or "")
    desc = str(fields.get("description") or "")
    text = f"{summary}\n{desc}".strip()
    key = str(issue.get("key") or fields.get("key") or "unknown")
    return {
        "text": text,
        "metadata": {
            "source": "jira",
            "issue_key": key,
            "acl_principals": list(viewer_principals),
        },
    }


def notion_page_to_chunk(page: dict[str, Any], *, space_id: str, allowed_principals: list[str]) -> dict[str, Any]:
    title = str(page.get("title") or "")
    body = str(page.get("plain_text") or page.get("content") or "")
    text = f"{title}\n{body}".strip()
    pid = str(page.get("id") or page.get("page_id") or "")
    return {
        "text": text,
        "metadata": {
            "source": "notion",
            "page_id": pid,
            "space_id": space_id,
            "acl_principals": list(allowed_principals),
        },
    }
