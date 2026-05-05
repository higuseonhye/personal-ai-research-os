"""
SOTA Radar persistence + ingestion cycles (used by dashboard / workers).
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]


def _bootstrap_sys_path() -> None:
    import sys

    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))


SNAPSHOT_PATH = _ROOT / "data" / "radar_snapshots.jsonl"


def _load_pipeline_bits():
    import importlib.util

    _bootstrap_sys_path()

    def load(rel: str, name: str):
        path = _ROOT / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        return mod

    su = load("08_feedback_loop/sota_update_pipeline.py", "pa_sota_update_pipeline_cycle")
    emb = load("07_rag_system/embedding_store.py", "pa_emb_store_radar")
    lb = load("04_sota_engine/leaderboard.py", "pa_lb_radar")
    ax = load("04_sota_engine/arxiv_ingestor.py", "pa_arxiv_radar")
    st = load("04_sota_engine/paper_structurer.py", "pa_struct_radar")
    return ax.fetch_recent_papers, st.extract_structure, emb.get_default_embedding_store, lb.get_default_leaderboard


def _heuristic_score(structured: dict[str, Any]) -> float:
    method = str(structured.get("method", "") or "")
    metrics = str(structured.get("metrics", "") or "")
    novelty = math.tanh((len(method) + len(metrics)) / 900.0)
    return float(max(0.05, min(1.0, 0.52 + 0.35 * novelty)))


def _cluster_bucket(title: str) -> str:
    t = title.lower()
    for tag in ("retrieval", "rag", "agent", "llm", "reason", "forecast", "rank", "multimodal"):
        if tag in t:
            return tag
    return "other"


def load_recent_snapshots(limit: int = 50) -> list[dict[str, Any]]:
    if not SNAPSHOT_PATH.exists():
        return []
    lines = SNAPSHOT_PATH.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(x) for x in lines if x.strip()]
    return rows[-limit:]


def save_snapshot(snapshot: dict[str, Any]) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def load_leaderboard_history_tail(limit: int = 400) -> list[dict[str, Any]]:
    path = _ROOT / "data" / "leaderboard_history.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(x) for x in lines if x.strip()]
    return rows[-limit:]


def build_radar_snapshot(
    *,
    processed_papers: list[dict[str, Any]],
    leaderboard_rows: list[dict[str, Any]],
    embedding_meta_sample: list[dict[str, Any]],
    prev_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    titles = [str(p.get("title", "")) for p in processed_papers][:25]

    clusters = Counter(_cluster_bucket(str(m.get("title", ""))) for m in embedding_meta_sample[:500])
    embedding_clusters = [{"cluster": k, "count": v} for k, v in clusters.most_common()]

    best_rows = sorted(
        leaderboard_rows,
        key=lambda r: float(r.get("best_score", float("-inf"))),
        reverse=True,
    )
    current_best_model = ""
    current_best_score = float("-inf")
    top_task = ""
    if best_rows:
        top_task = str(best_rows[0].get("task", ""))
        current_best_model = str(best_rows[0].get("best_model", ""))
        current_best_score = float(best_rows[0].get("best_score", float("-inf")))

    prev_best = float(prev_snapshot.get("global_best_score", float("-inf"))) if prev_snapshot else float("-inf")
    delta = ""
    if math.isfinite(current_best_score) and math.isfinite(prev_best):
        if abs(prev_best) < 1e-9:
            delta = "n/a"
        else:
            delta = f"{((current_best_score - prev_best) / abs(prev_best)) * 100.0:.2f}%"

    hist = load_leaderboard_history_tail(120)
    recent_scores = [float(x.get("score", 0.0)) for x in hist[-40:]]
    if len(recent_scores) >= 8:
        slope = recent_scores[-1] - recent_scores[0]
        trend_signal = "rising" if slope > 0.02 else "declining" if slope < -0.02 else "stable"
    else:
        trend_signal = "stable"

    alerts: list[str] = []
    if prev_snapshot and isinstance(delta, str) and delta.endswith("%"):
        try:
            dv = float(delta.replace("%", ""))
            if dv >= 15.0:
                alerts.append(f"SOTA surge detected vs prior snapshot ({delta}).")
        except ValueError:
            pass
    if prev_snapshot:
        prev_clusters = {c["cluster"]: c["count"] for c in prev_snapshot.get("embedding_clusters", [])}
        for row in embedding_clusters:
            tag = row["cluster"]
            if tag not in prev_clusters and row["count"] >= 3:
                alerts.append(f"New embedding cluster emergence: '{tag}'.")

    snapshot = {
        "timestamp": ts,
        "task": top_task[:160],
        "new_papers": titles,
        "sota_change": {
            "previous_best": str(prev_snapshot.get("global_best_model", "")) if prev_snapshot else "",
            "new_best": current_best_model,
            "delta": delta if delta != "" else "first_snapshot",
        },
        "embedding_clusters": embedding_clusters,
        "trend_signal": trend_signal,
        "global_best_score": current_best_score if math.isfinite(current_best_score) else "",
        "global_best_model": current_best_model,
        "alerts": alerts,
        "processed_count": len(processed_papers),
    }
    return snapshot


def run_radar_single_cycle(
    *,
    query: str = "retrieval augmented generation OR agent OR llm OR ranking OR forecasting",
    max_results: int = 25,
) -> dict[str, Any]:
    fetch_recent_papers, extract_structure, get_embedding_store, get_leaderboard = _load_pipeline_bits()
    embedding_store = get_embedding_store()
    leaderboard = get_leaderboard()

    processed: list[dict[str, Any]] = []
    try:
        papers = fetch_recent_papers(query, max_results=max_results)
    except Exception:  # noqa: BLE001
        papers = []

    if papers and os.environ.get("PA_DISABLE_SOTA_RANKER", "").lower() not in ("1", "true", "yes"):
        try:
            rank_path = _ROOT / "04_sota_engine" / "sota_ranker.py"
            rspec = importlib.util.spec_from_file_location("pa_sota_ranker", rank_path)
            rmod = importlib.util.module_from_spec(rspec)
            assert rspec.loader
            rspec.loader.exec_module(rmod)
            papers = rmod.rank_papers(query, papers)
        except Exception:  # noqa: BLE001
            pass

    for paper in papers:
        structured = extract_structure(paper["summary"])
        embedding_store.add(
            text=paper["summary"],
            metadata={
                "title": paper["title"],
                "pdf_url": paper["pdf_url"],
                **structured,
            },
        )
        task_key = str(structured.get("problem", ""))[:512] or paper["title"][:256]
        model_key = str(structured.get("method", ""))[:256] or "unknown_method"
        score = _heuristic_score(structured)
        if "_relevance_score" in paper:
            score = float(max(score, float(paper.get("_relevance_score", 0.0))))
        leaderboard.update(task=task_key, model=model_key, score=score)
        processed.append(
            {
                "title": paper["title"],
                "task_key": task_key,
                "score": score,
                "rank_score": float(paper.get("_relevance_score", score)),
            }
        )

    leaderboard_rows = leaderboard.table_rows()
    meta_sample = embedding_store.all_metadata()
    prev = load_recent_snapshots(1)
    prev_snap = prev[-1] if prev else None
    snap = build_radar_snapshot(
        processed_papers=processed,
        leaderboard_rows=leaderboard_rows,
        embedding_meta_sample=meta_sample,
        prev_snapshot=prev_snap,
    )
    save_snapshot(snap)
    return {"snapshot": snap, "indexed": len(processed)}


def run_radar_update_loop(interval_sec: int = 3600, stop_event: Event | None = None) -> None:
    ev = stop_event or Event()
    while not ev.is_set():
        try:
            run_radar_single_cycle()
        except Exception:  # noqa: BLE001
            pass
        ev.wait(interval_sec)


def start_radar_background_loop(interval_sec: int = 3600) -> tuple[Thread, Event]:
    stop = Event()

    def worker():
        run_radar_update_loop(interval_sec=interval_sec, stop_event=stop)

    th = Thread(target=worker, name="sota-radar-loop", daemon=True)
    th.start()
    return th, stop

