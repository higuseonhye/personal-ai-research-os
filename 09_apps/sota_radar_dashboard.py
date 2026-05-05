"""Live SOTA Radar dashboard — papers, embeddings snapshot, leaderboard trends, alerts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

APPS = Path(__file__).resolve().parent
ROOT = APPS.parent
for p in (ROOT, APPS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from radar_pipeline import (  # noqa: E402
    load_leaderboard_history_tail,
    load_recent_snapshots,
    run_radar_single_cycle,
    start_radar_background_loop,
)


def _leaderboard_table_rows() -> list[dict]:
    import importlib.util

    path = ROOT / "04_sota_engine" / "leaderboard.py"
    spec = importlib.util.spec_from_file_location("lb_mod_dash", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod.get_default_leaderboard().table_rows()


def _embedding_meta_tail(limit: int = 400) -> list[dict]:
    import importlib.util

    path = ROOT / "07_rag_system" / "embedding_store.py"
    spec = importlib.util.spec_from_file_location("emb_mod_dash", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    meta = mod.get_default_embedding_store().all_metadata()
    return meta[-limit:]


def main() -> None:
    st.set_page_config(page_title="SOTA Radar", layout="wide")
    st.title("SOTA Radar — Live Research Intelligence")

    with st.sidebar:
        st.header("Controls")
        interval = st.slider("Background loop interval (minutes)", min_value=5, max_value=180, value=60)
        auto = st.toggle("Start hourly-style background loop (daemon thread)", value=False)
        if auto and not st.session_state.get("_radar_bg_started"):
            th, stop_ev = start_radar_background_loop(interval_sec=int(interval * 60))
            st.session_state["_radar_bg_started"] = True
            st.session_state["_radar_stop"] = stop_ev
            st.session_state["_radar_thread"] = th
            st.caption("Background ingestion running (daemon). Toggle off requires restart to fully stop.")
        if st.button("Run ingestion cycle now", type="primary"):
            with st.spinner("Fetching arXiv → structuring → embeddings → leaderboard…"):
                out = run_radar_single_cycle(max_results=15)
            st.success(f"Indexed {out['indexed']} papers; snapshot saved.")

    snaps = load_recent_snapshots(80)
    latest = snaps[-1] if snaps else {}

    st.subheader("SOTA Shift Alerts")
    alerts = list(latest.get("alerts", []))
    hist = load_leaderboard_history_tail(200)
    if len(hist) >= 6:
        last_scores = [float(x["score"]) for x in hist[-6:]]
        jump = last_scores[-1] - last_scores[0]
        if jump >= 0.15:
            alerts.append(f"Heuristic leaderboard surge detected (+{jump:.3f}) over recent entries.")
    if alerts:
        for a in alerts:
            st.warning(a)
    else:
        st.info("No alerts in the latest snapshot cycle.")

    col_a, col_b = st.columns((2, 1))

    with col_a:
        st.subheader("Leaderboard (best per task)")
        rows = _leaderboard_table_rows()
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.write("Leaderboard empty — run an ingestion cycle.")

    with col_b:
        st.subheader("Trend signal")
        st.metric("Latest radar trend", str(latest.get("trend_signal", "unknown")))
        st.metric(
            "Global best score (heuristic)",
            str(latest.get("global_best_score", "")),
        )

    st.subheader("Performance over time (leaderboard history)")
    hist_df = pd.DataFrame(hist)
    if not hist_df.empty and "ts" in hist_df.columns:
        hist_df["ts"] = pd.to_datetime(hist_df["ts"], utc=True, errors="coerce")
        hist_df = hist_df.dropna(subset=["ts"]).sort_values("ts")
        chart_df = hist_df.set_index("ts")[["score"]].astype(float)
        chart_df["score_ma"] = chart_df["score"].rolling(window=min(12, len(chart_df)), min_periods=1).mean()
        st.line_chart(chart_df[["score", "score_ma"]])
    else:
        st.write("No history yet.")

    st.subheader("Paper stream")
    papers = latest.get("new_papers") or []
    if papers:
        st.json(papers[:40])
    else:
        st.write("No snapshot papers yet.")

    st.subheader("Embedding clusters (keyword buckets)")
    clusters = latest.get("embedding_clusters") or []
    cdf = pd.DataFrame(clusters)
    if not cdf.empty:
        st.bar_chart(cdf.set_index("cluster")["count"])
    else:
        meta = _embedding_meta_tail(200)
        if meta:
            st.caption(f"Showing latest indexed titles ({len(meta)} entries).")
            st.json([m.get("title", "") for m in meta[-25:]])
        else:
            st.write("Embedding index empty.")

    st.subheader("Snapshot inspector")
    st.json({k: v for k, v in latest.items() if k != "new_papers"})


if __name__ == "__main__":
    main()
