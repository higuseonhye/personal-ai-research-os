"""
Personal AI Research OS — Streamlit entry.

Run from repo root:
  pip install -r requirements.txt
  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from research_os.engine import run_research_pipeline

st.set_page_config(page_title="Personal AI Research OS", layout="wide")
st.title("Personal AI Research OS")
st.caption("Query → research plan → sources → structured memo → problem / papers / insights / ideas / experiments")

query = st.text_input(
    "What problem are you exploring?",
    value="How to improve RAG retrieval quality?",
    placeholder="e.g. How to improve RAG retrieval quality?",
)

if st.button("Run Research", type="primary"):
    if not (query or "").strip():
        st.warning("Enter a question first.")
    else:
        try:
            with st.spinner("Planning → fetching sources → synthesizing (15–40s typical)…"):
                result, plan = run_research_pipeline(query.strip())
        except RuntimeError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:  # noqa: BLE001
            st.exception(e)
            st.stop()

        with st.expander("Internal research plan (LLM)", expanded=False):
            st.text(plan)

        st.subheader("Problem")
        st.write(result.get("problem", ""))

        st.subheader("Key papers / sources")
        for p in result.get("papers") or []:
            st.markdown(f"- {p}")

        st.subheader("Insights")
        for item in result.get("insights") or []:
            st.markdown(f"- {item}")

        st.subheader("New ideas")
        for item in result.get("ideas") or []:
            st.markdown(f"- {item}")

        st.subheader("Experiment plan")
        for item in result.get("experiments") or []:
            st.markdown(f"- {item}")
