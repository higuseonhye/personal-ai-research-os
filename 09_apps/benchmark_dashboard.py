"""Streamlit viewer for benchmark history (SQLite or Postgres via BENCHMARK_BACKEND)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
APPS = Path(__file__).resolve().parent
for p in (ROOT, APPS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def main() -> None:
    st.set_page_config(page_title="Enterprise benchmarks", layout="wide")
    st.title("Enterprise benchmark runs")

    from importlib.util import module_from_spec, spec_from_file_location

    be_spec = spec_from_file_location("benchmark_backend_ui", ROOT / "08_feedback_loop" / "benchmark_backend.py")
    be_mod = module_from_spec(be_spec)
    assert be_spec.loader
    be_spec.loader.exec_module(be_mod)
    store = be_mod.load_benchmark_store()

    backend = os.environ.get("BENCHMARK_BACKEND", "sqlite").strip().lower()
    st.caption(
        f"Backend: `{backend}` — set `BENCHMARK_BACKEND`, `DATABASE_URL` (Postgres), "
        "`PA_TENANT_ID`, `PA_BENCHMARK_DB` as needed."
    )

    tid_default = os.environ.get("PA_TENANT_ID", "default")
    tenant_id = st.sidebar.text_input("Tenant id", value=tid_default)

    db_default = store.default_benchmark_db_path()
    db_help = "SQLite DB path (ignored when backend=postgres)" if backend == "postgres" else "SQLite DB path"
    db_input = st.text_input(db_help, value=str(db_default))
    db_path = Path(db_input)

    runs = store.list_recent_runs(limit=100, db_path=db_path, tenant_id=tenant_id.strip() or None)
    if not runs:
        st.info(
            "No runs yet. Example:\n\n"
            "`python scripts/run_benchmark_scheduler.py --dataset data/enterprise_eval_sample.jsonl --once`\n\n"
            f"Default DB: `{db_default}`"
        )
        return

    df = pd.DataFrame(runs)
    st.subheader("Recent runs")
    st.dataframe(df, use_container_width=True, hide_index=True)

    ids = sorted({int(r["run_id"]) for r in runs}, reverse=True)
    rid = st.selectbox("Inspect run_id", ids)

    run_row = store.get_run_by_id(rid, db_path=db_path, tenant_id=tenant_id.strip() or None) or {}
    with st.expander("Run provenance (git / dataset identity)"):
        st.json(
            {
                "run_id": rid,
                "tenant_id": run_row.get("tenant_id"),
                "git_commit": run_row.get("git_commit"),
                "dataset_digest": run_row.get("dataset_digest"),
                "dataset_version": run_row.get("dataset_version"),
                "dataset_path": run_row.get("dataset_path"),
                "pipeline_mode": run_row.get("pipeline_mode"),
                "limit_n": run_row.get("limit_n"),
                "started_at": run_row.get("started_at"),
                "finished_at": run_row.get("finished_at"),
                "notes": run_row.get("notes"),
            }
        )

    exp_path = ROOT / "08_feedback_loop" / "benchmark_metrics_export.py"
    es = spec_from_file_location("benchmark_metrics_export_ui", exp_path)
    exporter = module_from_spec(es)
    assert es.loader
    es.loader.exec_module(exporter)
    tid_scope = tenant_id.strip() or None
    prom = exporter.export_run_prometheus(rid, db_path=db_path, tenant_id=tid_scope)
    with st.expander("Prometheus textfile excerpt (for Grafana Agent)"):
        st.code(prom, language="prometheus")

    rows = store.fetch_results(rid, db_path=db_path, tenant_id=tid_scope)
    if not rows:
        st.warning("No rows for this run.")
        return
    rdf = pd.DataFrame(rows)
    st.subheader(f"Results for run {rid}")
    drop_cols = [c for c in ("summary",) if c in rdf.columns]
    st.dataframe(rdf.drop(columns=drop_cols, errors="ignore"), use_container_width=True, hide_index=True)

    failures = [r for r in rows if not r.get("ok")]
    if failures:
        st.error(f"{len(failures)} failures")
        st.json(
            [
                {
                    "datapoint_id": x.get("datapoint_id"),
                    "failure_category": x.get("failure_category"),
                    "assertions_passed": x.get("assertions_passed"),
                    "error": x.get("error"),
                }
                for x in failures[:50]
            ]
        )


if __name__ == "__main__":
    main()
