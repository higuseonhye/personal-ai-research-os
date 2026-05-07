"""Human-readable strings for CLI and Streamlit (no raw JSON dumps in user-facing flow)."""

from __future__ import annotations

from typing import Any


def humanize_method(mid: str) -> str:
    return mid.replace("_", " ")


def format_problem(req: dict[str, Any]) -> str:
    lines = [
        f"What we are solving: {req.get('problem', 'Unspecified problem')}",
        f"Constraints: {', '.join(req.get('constraints') or ['none stated'])}",
        f"Goal: {req.get('goal', 'unspecified')}",
    ]
    return "\n".join(lines)


def format_system_design(structured: dict[str, Any], composition: dict[str, Any], architecture: str) -> str:
    strategy = composition.get("strategy") or []
    readable = ", ".join(humanize_method(m) for m in strategy) or "baseline stack"
    challenges = ", ".join(structured.get("key_challenges") or [])
    metrics = ", ".join(structured.get("metrics") or [])
    reason = composition.get("reason") or "Curated default composition."

    parts = [
        f"Use case: {structured.get('use_case', 'unknown')}",
        f"Key challenges: {challenges or 'n/a'}",
        f"Strategy (methods): {readable}",
        f"Why this stack: {reason}",
        f"Architecture: {architecture}",
        f"Design metrics: {metrics or 'n/a'}",
    ]
    return "\n".join(parts)


def format_plan(steps: list[str]) -> str:
    return "\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps))


def format_evaluation(targets: dict[str, str]) -> str:
    parts = [f"Accuracy target: {targets.get('accuracy_target', 'n/a')}"]
    if "latency_target" in targets:
        parts.append(f"Latency target: {targets['latency_target']}")
    return "\n".join(parts)


def print_cli_report(bundle: dict[str, Any]) -> None:
    """Stdio-friendly section headers matching product spec."""
    req = bundle["requirement"]
    structured = bundle["structured"]
    composition = bundle["composition"]
    print("=== PROBLEM ===")
    print(format_problem(req))
    print()

    print("=== SYSTEM DESIGN ===")
    print(format_system_design(structured, composition, bundle["architecture"]))
    print()

    print("=== EXECUTION PLAN ===")
    print(format_plan(bundle["plan"]))
    print()

    print("=== EVALUATION ===")
    print(format_evaluation(bundle["targets"]))
    print()

    if bundle.get("memory_id"):
        print("(Saved to solution memory.)")
