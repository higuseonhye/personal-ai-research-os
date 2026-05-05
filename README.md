# Personal AI Research & Execution OS

Local-first Python toolkit for turning **customer problems → structured research tasks → multi-system experiments → evaluation → insights → durable memory**.

## Principles

- **One interface for every system:** `AISystem.run(input: dict) -> SystemOutput` for retrieval, LLM/RAG, multimodal, agents, and business models.
- **Reproducible runs:** seeded experiments, JSONL logs, SQLite memory.
- **No SaaS requirement:** metrics, local judge proxies, and template QA run without external APIs (you can swap in your own models later).

## Screenshots

**Enterprise pipeline** (`streamlit run 09_apps/streamlit_ui.py`) and **benchmark runs** (`streamlit run 09_apps/benchmark_dashboard.py`) — representative layouts:

![Enterprise pipeline (left) and benchmark dashboard (right)](assets/readme-dashboards.png)

**SOTA Radar** (`streamlit run 09_apps/sota_radar_dashboard.py`): arXiv ingestion cycles, leaderboard trends, snapshots; **Paper stream** lists **Abstract** and **PDF** links when URLs are present.

![SOTA Radar — paper stream with source links](assets/sota-radar-dashboard.png)

**Research IR dashboard** (`streamlit run ui/app.py`): compile a problem, pick systems, paste JSON input, then review results in the **Results** tab.

![Research OS — Problem & systems tab](assets/research-os-dashboard.png)

## Layout

| Path | Purpose |
|------|---------|
| `09_apps/` | Streamlit apps: enterprise pipeline, benchmark history, SOTA radar. |
| `pipeline.py` | Enterprise runner (full / LangGraph / production entrypoints). |
| `problem_compiler/` | Natural language → structured task (domain, hypotheses, suggested systems). |
| `system_registry/` | `AISystem` implementations and registry. |
| `experiment_engine/` | Run the same input across selected systems; append-only logs under `data/logs/`. |
| `evaluation_engine/` | Recall@k, MRR, nDCG@k, accuracy-style checks, local judge dimensions, pairwise comparisons. |
| `insight_engine/` | Research-style narrative: best system, ranking, hypotheses, next steps, failure hooks. |
| `memory/` | SQLite store for experiments, evaluations, insights, failures, and performance history. |
| `ui/` | Streamlit dashboard for fast iteration. |
| `main.py` | CLI demo of the full pipeline. |

## Requirements

- **Python 3.10+** (3.10–3.12 recommended for `torch` / `sentence-transformers` stability).

## Install

From the directory that **contains** this folder (if this repo is named `research_os` inside a parent project):

```bash
pip install -r research_os/requirements.txt
```

If you cloned this repo so that **this folder is your project root** (this README sits next to `main.py`):

```bash
pip install -r requirements.txt
```

## Run

**CLI (one-shot pipeline):**

```bash
# From repo root (this folder is next to main.py):
python main.py --systems BM25Retriever DenseRetriever HybridRetriever
```

**Streamlit UIs:**

```bash
# Enterprise problem → decomposition → SOTA → architecture → eval → iteration
streamlit run 09_apps/streamlit_ui.py

# Benchmark history (SQLite / Postgres via env)
streamlit run 09_apps/benchmark_dashboard.py

# SOTA radar (papers / leaderboard snapshots)
streamlit run 09_apps/sota_radar_dashboard.py

# Research OS — IR-style experiments across registered systems
streamlit run ui/app.py
```

Use **`09_apps/streamlit_ui`** for the JSON-first enterprise pipeline. Use **`ui/app`** — **Problem & systems** tab to compile a problem, pick systems, paste JSON input (IR-style: `query`, `corpus`, optional `relevant_ids`, `top_k`), then run. Open **Results** for tables, pairwise output, insights, and failure snapshots.

## Input hints

- **IR-style systems** expect keys like `query`, `corpus` (`[{ "id", "text" }]`), optional `relevant_ids` for metrics, and `top_k`.
- **LLM/RAG** expect `question` and usually `corpus` for `RAGSystem`.
- **Agents** expect `task` (and optional `tools`).
- **Business** models expect their documented keys (`candidates`, `rows`, `catalog`, etc.)—see `system_registry/systems/`.

## Adding a system

1. Subclass `AISystem` in `system_registry/systems/`.
2. Register in `get_default_registry()` in `system_registry/registry.py`.
3. Optionally extend `ProblemCompiler` so new systems appear in `suggested_systems`.

## License

Released under the [MIT License](LICENSE).
