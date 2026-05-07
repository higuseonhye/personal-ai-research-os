"""
Unified Streamlit entry: Solution Design OS + legacy research OS apps.

Run from repo root:
  streamlit run 09_apps/research_os_hub.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = Path(__file__).resolve().parent
for p in (ROOT, APPS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import streamlit as st  # noqa: E402

from benchmark_dashboard import render_benchmark_dashboard  # noqa: E402
from sota_radar_dashboard import render_sota_radar_dashboard  # noqa: E402
from streamlit_ui import render_enterprise_pipeline  # noqa: E402

from core.design_os_pipeline import run_design_os  # noqa: E402
from core.design_os_present import (  # noqa: E402
    format_evaluation,
    format_plan,
    format_problem,
    format_system_design,
)


def render_solution_design_os() -> None:
    st.title("AI Solution Design OS")
    st.caption("Problem in → structured system design and execution plan (same logic as `python main.py`).")

    demo = "Build internal document QA system with high accuracy under noisy data"
    problem = st.text_area("Describe your problem", value=demo, height=100)

    persist = st.checkbox("Save run to solution memory (`data/solution_design_memory.json`)", value=True)

    if st.button("Design system", type="primary"):
        with st.spinner("Running requirement → structuring → research → composition → plan → evaluation…"):
            bundle = run_design_os(problem, persist_memory=persist)

        st.subheader("Problem (parsed)")
        st.text(format_problem(bundle["requirement"]))

        st.subheader("System design")
        st.text(
            format_system_design(
                bundle["structured"],
                bundle["composition"],
                bundle["architecture"],
            )
        )

        st.subheader("Execution plan")
        st.text(format_plan(bundle["plan"]))

        st.subheader("Evaluation targets")
        st.text(format_evaluation(bundle["targets"]))

        if bundle.get("memory_id"):
            st.success(f"Saved to memory (`id`: {bundle['memory_id']})")

        with st.expander("Internal research hints (developer view)"):
            st.json(bundle.get("research", {}))


def main() -> None:
    st.set_page_config(page_title="Personal AI Research OS — Hub", layout="wide")
    st.sidebar.title("Programs")
    app = st.sidebar.radio(
        "Open",
        [
            "Solution Design OS",
            "Enterprise pipeline",
            "Benchmark dashboard",
            "SOTA Radar",
        ],
        label_visibility="collapsed",
    )

    if app == "Solution Design OS":
        render_solution_design_os()
    elif app == "Enterprise pipeline":
        render_enterprise_pipeline()
    elif app == "Benchmark dashboard":
        render_benchmark_dashboard()
    else:
        render_sota_radar_dashboard()


if __name__ == "__main__":
    main()
