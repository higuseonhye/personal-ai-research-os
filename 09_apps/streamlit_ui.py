"""Minimal Streamlit UI for the enterprise PM / FDE pipeline."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(rel: str, mod_name: str) -> object:
    p = ROOT / rel
    spec = importlib.util.spec_from_file_location(mod_name, p)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(m)
    return m


def render_enterprise_pipeline() -> None:
    import streamlit as st

    st.title("Personal AI Research OS — Enterprise pipeline")
    problem = st.text_area(
        "Enterprise problem",
        value="Reduce customer support cost in SaaS product",
        height=120,
    )
    if st.button("Run pipeline", type="primary"):
        pipe = _load("pipeline.py", "pa_pipeline_runner")
        with st.spinner("Running decomposition → SOTA → architecture → eval → iteration…"):
            out = pipe.run_full_pipeline(problem)
        st.subheader("Structured output (JSON-first)")
        st.json(out)


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Personal AI Research OS", layout="wide")
    render_enterprise_pipeline()


if __name__ == "__main__":
    main()
