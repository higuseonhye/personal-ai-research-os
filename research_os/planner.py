"""Turn a user query into a short research plan with sub-questions (LLM)."""

from __future__ import annotations

from openai import OpenAI

from research_os.settings import get_openai_client, get_model


def create_research_plan(query: str) -> str:
    """
    Expand the query into a concise research plan with 3–5 sub-questions.
    Returns plain text (used as input to retrieval + synthesis).
    """
    query = (query or "").strip()
    if not query:
        return "Plan: (empty query — ask a specific research question.)"

    client: OpenAI = get_openai_client()
    model = get_model()

    system = (
        "You are a research lead. Given a question, produce a tight research plan:\n"
        "1) One sentence clarifying the problem.\n"
        "2) Exactly 3–5 concrete sub-questions to investigate.\n"
        "Keep under 250 words. Plain text, no markdown headings."
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
        temperature=0.4,
        max_tokens=500,
    )
    text = (resp.choices[0].message.content or "").strip()
    return text if text else f"Plan: investigate: {query}"
