"""
Structured benchmark assertions + failure taxonomy for release-gate style evaluation.

Datapoint optional fields (JSONL):
  assert_readiness_min: float (0-1), optional
  assert_must_include_substrings: list[str], optional (case-insensitive match in blob)
  assert_expected_subproblems_min: int, optional minimum count of technical subproblems
"""

from __future__ import annotations

from typing import Any

# Taxonomy for SQL filters / dashboards
FAILURE_NONE = "none"
FAILURE_PIPELINE = "pipeline_error"
FAILURE_TIMEOUT = "timeout"
FAILURE_IMPORT = "import_error"
FAILURE_ASSERTION = "assertion_violation"
FAILURE_MISSING_FIELD = "missing_input"


def classify_exception(exc: BaseException) -> str:
    msg = str(exc).lower()
    if isinstance(exc, TimeoutError):
        return FAILURE_TIMEOUT
    if "modulenotfound" in type(exc).__name__.lower() or "no module named" in msg:
        return FAILURE_IMPORT
    if "timeout" in msg:
        return FAILURE_TIMEOUT
    return FAILURE_PIPELINE


def _blob_from_result(result: dict[str, Any]) -> str:
    parts: list[str] = []
    dec = result.get("decomposition") or {}
    if isinstance(dec, dict):
        parts.append(str(dec.get("interpreted_goal", "")))
        parts.append(str(dec.get("raw_problem", "")))
        for k in ("technical_subproblems", "subproblems"):
            for s in dec.get(k) or []:
                parts.append(str(s))
    arch = result.get("architecture") or {}
    if isinstance(arch, dict):
        parts.append(str(arch.get("system_design", arch.get("architecture", ""))))
        for c in arch.get("components") or []:
            parts.append(str(c))
    ev = result.get("evaluation") or {}
    parts.append(str(ev.get("eval_strategy", "")))
    return "\n".join(parts).lower()


def _readiness(result: dict[str, Any]) -> float | None:
    ev = result.get("evaluation") or {}
    rs = ev.get("readiness_score")
    if rs is None and isinstance(ev.get("_legacy"), dict):
        rs = ev["_legacy"].get("readiness_score")
    if rs is None:
        return None
    try:
        return float(str(rs).strip().replace("%", ""))
    except ValueError:
        return None


def run_assertions(datapoint: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """
    Returns {passed: bool, violations: list[str], checks: list[dict]}.
    """
    checks: list[dict[str, Any]] = []
    violations: list[str] = []

    rmin = datapoint.get("assert_readiness_min")
    if rmin is not None and str(rmin).strip() != "":
        try:
            need = float(rmin)
            got = _readiness(result)
            ok = got is not None and got >= need
            checks.append({"id": "readiness_min", "need": need, "got": got, "pass": ok})
            if not ok:
                violations.append(f"readiness_min: need>={need}, got={got}")
        except ValueError:
            checks.append({"id": "readiness_min", "error": "invalid_assert_readiness_min", "pass": False})
            violations.append("invalid assert_readiness_min")

    needles = datapoint.get("assert_must_include_substrings") or []
    if isinstance(needles, str):
        needles = [needles]
    if needles:
        blob = _blob_from_result(result)
        for n in needles:
            nn = str(n).lower().strip()
            if not nn:
                continue
            ok = nn in blob
            checks.append({"id": f"substring:{nn[:40]}", "pass": ok})
            if not ok:
                violations.append(f"missing_substring:{nn}")

    exp = datapoint.get("expected_technical_decomposition") or []
    if isinstance(exp, list) and exp:
        dec = result.get("decomposition") or {}
        subs = list(dec.get("technical_subproblems") or dec.get("subproblems") or [])
        joined = " ".join(str(s).lower() for s in subs)
        for tag in exp:
            t = str(tag).lower().strip()
            if not t:
                continue
            ok = t in joined
            checks.append({"id": f"expected_subproblem:{t}", "pass": ok})
            if not ok:
                violations.append(f"missing_expected_subproblem:{t}")

    min_sp = datapoint.get("assert_expected_subproblems_min")
    if min_sp is not None and str(min_sp).strip() != "":
        try:
            need_n = int(min_sp)
            dec = result.get("decomposition") or {}
            subs = dec.get("technical_subproblems") or dec.get("subproblems") or []
            n = len(subs) if isinstance(subs, list) else 0
            ok = n >= need_n
            checks.append({"id": "subproblems_min", "need": need_n, "got": n, "pass": ok})
            if not ok:
                violations.append(f"subproblems_min: need>={need_n}, got={n}")
        except ValueError:
            violations.append("invalid assert_expected_subproblems_min")

    passed = len(violations) == 0
    return {"passed": passed, "violations": violations, "checks": checks}
