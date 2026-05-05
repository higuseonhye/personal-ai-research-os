"""Live SOTA Radar dashboard — papers, embeddings snapshot, leaderboard trends, alerts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

APPS = Path(__file__).resolve().parent
ROOT = APPS.parent
for p in (ROOT, APPS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from radar_pipeline import (  # noqa: E402
    abs_url_from_pdf_url,
    load_leaderboard_history_tail,
    load_recent_snapshots,
    run_radar_single_cycle,
    start_radar_background_loop,
)


def _normalize_paper_stream(rows: list[Any]) -> list[dict[str, str]]:
    """Support legacy snapshots where `new_papers` was a list of title strings."""
    out: list[dict[str, str]] = []
    for r in rows:
        if isinstance(r, dict):
            pdf = str(r.get("pdf_url", "") or "")
            abs_u = str(r.get("abs_url", "") or "") or abs_url_from_pdf_url(pdf)
            out.append(
                {
                    "title": str(r.get("title", "")),
                    "pdf_url": pdf,
                    "abs_url": abs_u,
                    "source": str(r.get("source", "") or ("arxiv" if "arxiv.org" in pdf.lower() else "")),
                }
            )
        else:
            out.append({"title": str(r), "pdf_url": "", "abs_url": "", "source": ""})
    return out


def _paper_stream_markdown(entries: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for i, e in enumerate(entries[:40], start=1):
        title = e.get("title", "").strip() or "(untitled)"
        abs_u = (e.get("abs_url") or "").strip()
        pdf_u = (e.get("pdf_url") or "").strip()
        bits: list[str] = []
        if abs_u:
            bits.append(f"[Abstract]({abs_u})")
        if pdf_u:
            bits.append(f"[PDF]({pdf_u})")
        suffix = " · ".join(bits) if bits else "*no URL stored*"
        lines.append(f"{i}. **{title}** — {suffix}")
    return "\n\n".join(lines)


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
        try:
            import arxiv  # noqa: F401
        except ImportError:
            st.warning(
                "The `arxiv` package is not installed. Install it for live paper fetch: "
                "`pip install arxiv` (see requirements.txt). Cycles still save snapshots with 0 new papers."
            )
        interval = st.slider("Background loop interval (minutes)", min_value=5, max_value=180, value=60)
        auto = st.checkbox(
            "Start hourly-style background loop (daemon thread)",
            value=False,
            key="_radar_bg_checkbox",
        )
        if auto and not st.session_state.get("_radar_bg_started"):
            th, stop_ev = start_radar_background_loop(interval_sec=int(interval * 60))
            st.session_state["_radar_bg_started"] = True
            st.session_state["_radar_stop"] = stop_ev
            st.session_state["_radar_thread"] = th
            st.caption("Background ingestion running (daemon). Unchecking the box does not stop the thread; restart the app to stop.")
        if st.button("Run ingestion cycle now", type="primary"):
            with st.spinner("Fetching arXiv → structuring → embeddings → leaderboard…"):
                out = run_radar_single_cycle(max_results=15)
            ix = int(out.get("indexed") or 0)
            if ix == 0:
                st.info("Indexed 0 papers; snapshot still saved. Install `arxiv` if you expected live arXiv results.")
            else:
                st.success(f"Indexed {ix} papers; snapshot saved.")

    snaps = load_recent_snapshots(80)
    latest: dict = snaps[-1] if snaps else {}

    if not snaps:
        st.info(
            "**No radar snapshots yet.** After you run **Run ingestion cycle now** in the sidebar, "
            "this page reads `data/radar_snapshots.jsonl`. "
            "With `pip install arxiv`, each cycle fetches papers, updates embeddings, and fills the leaderboard. "
            "Without `arxiv`, cycles still append a snapshot but index **0** papers."
        )

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
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
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
        norm = _normalize_paper_stream(list(papers))
        st.markdown(_paper_stream_markdown(norm))
        with st.expander("Raw entries (copy-friendly)"):
            st.json(norm[:40])
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
            st.caption(f"Latest indexed papers ({len(meta)} entries in store) with source links where present.")
            emb_rows = []
            for m in meta[-25:]:
                pdf = str(m.get("pdf_url", "") or "")
                emb_rows.append(
                    {
                        "title": str(m.get("title", "") or ""),
                        "pdf_url": pdf,
                        "abs_url": abs_url_from_pdf_url(pdf),
                    }
                )
            st.markdown(_paper_stream_markdown(emb_rows))
            with st.expander("Embedding metadata (JSON)"):
                st.json(emb_rows)
        else:
            st.write("Embedding index empty.")

    st.subheader("Snapshot inspector")
    if not latest:
        st.caption("Nothing to show until at least one ingestion cycle has been saved to `data/radar_snapshots.jsonl`.")
    else:
        st.json({k: v for k, v in latest.items() if k != "new_papers"})


if __name__ == "__main__":
    main()
