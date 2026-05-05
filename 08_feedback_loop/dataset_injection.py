"""
Load / validate / merge enterprise evaluation datasets (JSONL) for benchmark injection.

Optional benchmark assertion keys (per datapoint), normalized by `normalize_row`:
  assert_readiness_min — float threshold on readiness_score (when present).
  assert_must_include_substrings — list[str]; matched case-insensitively in pipeline output blob.
  assert_expected_subproblems_min — int minimum technical subproblem count.
"""

from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path
from typing import Any, Literal

REQUIRED_KEYS = {
    "id",
    "enterprise_problem",
    "domain",
    "context",
    "constraints",
    "expected_technical_decomposition",
    "gold_solution_pattern",
    "evaluation_metrics",
    "difficulty_level",
}

Difficulty = Literal["low", "medium", "high", "frontier"]


def _validate_row(row: dict[str, Any], strict: bool = True) -> list[str]:
    errors: list[str] = []
    for k in REQUIRED_KEYS:
        if k not in row:
            errors.append(f"missing:{k}")
    if "difficulty_level" in row and str(row["difficulty_level"]) not in (
        "low",
        "medium",
        "high",
        "frontier",
    ):
        errors.append("invalid:difficulty_level")
    for k in ("constraints", "expected_technical_decomposition", "evaluation_metrics"):
        if k in row and not isinstance(row[k], list):
            errors.append(f"type:{k}_must_be_list")
    if strict and errors:
        raise ValueError("; ".join(errors))
    return errors


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def load_dataset(path: Path) -> list[dict[str, Any]]:
    sfx = path.suffix.lower()
    if sfx == ".jsonl":
        return load_jsonl(path)
    if sfx == ".csv":
        return load_csv(path)
    if sfx == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return list(raw)
        raise ValueError("JSON dataset must be a list of objects")
    raise ValueError(f"Unsupported format: {sfx}")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if not out.get("id"):
        out["id"] = str(uuid.uuid4())
    if not out.get("difficulty_level"):
        out["difficulty_level"] = "medium"
    if isinstance(out.get("constraints"), str):
        out["constraints"] = [out["constraints"]]
    if isinstance(out.get("evaluation_metrics"), str):
        out["evaluation_metrics"] = [out["evaluation_metrics"]]
    if isinstance(out.get("expected_technical_decomposition"), str):
        out["expected_technical_decomposition"] = [out["expected_technical_decomposition"]]

    if "assert_readiness_min" in out and out["assert_readiness_min"] is not None:
        try:
            out["assert_readiness_min"] = float(out["assert_readiness_min"])
        except (TypeError, ValueError):
            pass
    if "assert_expected_subproblems_min" in out and out["assert_expected_subproblems_min"] is not None:
        try:
            out["assert_expected_subproblems_min"] = int(out["assert_expected_subproblems_min"])
        except (TypeError, ValueError):
            pass
    amis = out.get("assert_must_include_substrings")
    if isinstance(amis, str):
        out["assert_must_include_substrings"] = [amis]
    elif amis is not None and not isinstance(amis, list):
        out["assert_must_include_substrings"] = [str(amis)]

    return out


def merge_datasets(*parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for part in parts:
        for row in part:
            r = normalize_row(row)
            _validate_row(r, strict=True)
            rid = str(r["id"])
            if rid in seen:
                continue
            seen.add(rid)
            merged.append(r)
    return merged


def export_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
