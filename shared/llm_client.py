"""OpenAI / Anthropic JSON completion with deterministic local fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if m:
        text = m.group(0)
    return json.loads(text)


def _openai_json(system: str, user: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_JSON_MODEL", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    content = resp.choices[0].message.content or "{}"
    return _extract_json_object(content)


def _anthropic_json(system: str, user: str) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.environ.get("ANTHROPIC_JSON_MODEL", "claude-3-5-haiku-20241022"),
        max_tokens=4096,
        system=system + "\nRespond with a single JSON object only, no markdown.",
        messages=[{"role": "user", "content": user}],
    )
    blocks = msg.content
    text = "".join(getattr(b, "text", "") for b in blocks)
    return _extract_json_object(text)


def json_llm_complete(
    system_prompt: str,
    user_prompt: str,
    model_cls: type[T],
    *,
    fallback_builder: dict[str, Any] | None = None,
) -> T:
    """
    Return a validated instance of model_cls. Uses OpenAI, then Anthropic, then fallback_builder.
    """
    data: dict[str, Any] | None = None
    last_err: Exception | None = None
    if os.environ.get("OPENAI_API_KEY"):
        try:
            data = _openai_json(system_prompt, user_prompt)
        except Exception as e:  # noqa: BLE001
            last_err = e
    if data is None and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            data = _anthropic_json(system_prompt, user_prompt)
        except Exception as e:  # noqa: BLE001
            last_err = e
    if data is None:
        data = dict(fallback_builder or {})
    try:
        return model_cls.model_validate(data)
    except ValidationError:
        if fallback_builder is not None:
            return model_cls.model_validate(dict(fallback_builder))
        if last_err:
            raise last_err
        raise


def json_llm_complete_dict(
    system_prompt: str,
    user_prompt: str,
    model_cls: type[T],
    *,
    fallback_builder: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return json_llm_complete(
        system_prompt,
        user_prompt,
        model_cls,
        fallback_builder=fallback_builder,
    ).model_dump()
