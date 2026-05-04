"""
Streamlit research dashboard — fast iteration UX.
Run from repository root:
  streamlit run research_os/ui/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from research_os.evaluation_engine import evaluate_record
from research_os.experiment_engine import ExperimentEngine
from research_os.insight_engine import InsightEngine
from research_os.memory import ResearchMemory
from research_os.problem_compiler import ProblemCompiler
from research_os.system_registry import get_default_registry

DEFAULT_CORPUS = [
    {"id": "d1", "text": "Enterprise VPN requires MFA and device compliance checks."},
    {"id": "d2", "text": "Catering orders for all-hands are due on Tuesdays."},
    {"id": "d3", "text": "Privileged access reviews occur quarterly for SOC2."},
]

st.set_page_config(page_title="Research OS", layout="wide")
st.title("Personal AI Research & Execution OS")
st.caption("Local-first: problem → systems → experiment → evaluation → insight → memory")

compiler = ProblemCompiler()
registry = get_default_registry()
exp_engine = ExperimentEngine(registry)
insight_engine = InsightEngine()
memory = ResearchMemory()

with st.sidebar:
    st.header("Run")
    seed = st.number_input("Experiment seed", value=42, step=1)
    top_k = st.number_input("top_k", value=5, min_value=1, max_value=50)

tab_problem, tab_results = st.tabs(["Problem & systems", "Results"])

with tab_problem:
    problem = st.text_area(
        "Customer / business problem",
        value="Search results are not accurate for enterprise documents",
        height=100,
    )
    if st.button("Compile problem"):
        st.session_state["task"] = compiler.compile(problem)
    task = st.session_state.get("task")
    if task:
        st.subheader("Structured task")
        st.json(task.to_dict())

    all_ids = registry.list_ids()
    default_pick = task.suggested_systems if task else ["BM25Retriever", "DenseRetriever", "HybridRetriever"]
    default_pick = [x for x in default_pick if x in all_ids]
    systems = st.multiselect("Systems to compare", options=all_ids, default=default_pick or all_ids[:3])

    st.subheader("Experiment input (JSON)")
    default_inp = {
        "query": "What controls exist for remote access to enterprise systems?",
        "corpus": DEFAULT_CORPUS,
        "relevant_ids": ["d1", "d3"],
        "top_k": int(top_k),
    }
    inp_raw = st.text_area("input_json", value=json.dumps(default_inp, indent=2), height=220)
    run = st.button("Run experiment", type="primary")

if run:
    try:
        inp = json.loads(inp_raw)
        inp["top_k"] = int(inp.get("top_k", top_k))
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

    task = compiler.compile(problem)
    st.session_state["task"] = task
    if not systems:
        st.error("Select at least one system.")
        st.stop()

    with st.spinner("Running systems…"):
        record = exp_engine.run_single(systems, inp, seed=int(seed))
        bundle = evaluate_record(record, inp, k=int(inp.get("top_k", 10)))
        report = insight_engine.generate(task, record, bundle, input_snapshot=inp)
        memory.persist_run(task, record, bundle, report)
        st.session_state["last_record"] = record
        st.session_state["last_bundle"] = bundle
        st.session_state["last_report"] = report
    st.success("Experiment finished — open the Results tab.")

with tab_results:
    if "last_bundle" not in st.session_state:
        st.info("Compile a problem, select systems, run the experiment from the first tab, then return here.")
    else:
        bundle = st.session_state["last_bundle"]
        report = st.session_state["last_report"]
        record = st.session_state["last_record"]

        st.subheader("Comparison table")
        rows = []
        for p in bundle.per_system:
            row = {
                "system_id": p.system_id,
                "success": p.success,
                **p.metrics,
                **{f"judge_{k}": v for k, v in p.judge.items()},
            }
            rows.append(row)
        st.dataframe(rows, use_container_width=True)

        st.subheader("Pairwise (forced choice)")
        st.json(bundle.pairwise)

        st.subheader("Rankings (insight engine composite)")
        st.json(report.to_dict()["ranking"])

        st.subheader("Research insights")
        for line in report.reasoning:
            st.write(line)
        with st.expander("Hypothesis status"):
            st.json(report.hypothesis_status)
        with st.expander("Suggested next steps"):
            for n in report.next_steps:
                st.write(f"- {n}")

        st.subheader("Failure cases (this run)")
        st.json(report.failure_cases[:20])

        st.subheader("Recent failures from DB")
        st.json(memory.recent_failure_cases(15))

        st.subheader("Raw experiment log (last run)")
        st.json(record.to_dict())
