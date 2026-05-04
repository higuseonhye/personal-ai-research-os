# Coding agent session — Research OS (YC Summer 2026 optional attachment)

**Tooling:** Cursor (agent mode), human review on architecture and evaluation semantics.  
**Format:** Narrative export summarizing the session goals, decisions, and shipped outcome (not a raw verbatim transcript).

---

## 1. Problem statement (what we asked the agent to build)

Build a **local-first “Personal AI Research & Execution Operating System”** for a single advanced operator (AI architect, applied researcher, forward-deployed engineer, experiment owner)—**not a SaaS**.

The system must support the loop:

**Customer problem → structured research task → run multiple AI systems → controlled experiments → evaluation → insights → durable memory**

**Universal constraint:** every capability is an **`AISystem`**: `run(input: dict) -> output`—including IR, LLM/RAG, multimodal, agents, and business-style models. No special-case architecture per domain.

---

## 2. Session goals (acceptance criteria)

1. **Modular packages:** `problem_compiler/`, `system_registry/`, `experiment_engine/`, `evaluation_engine/`, `insight_engine/`, `memory/`, `ui/` (Streamlit), `data/`, `main.py`.
2. **Registry + interface:** abstract `AISystem` + concrete systems (BM25, dense, hybrid, ColBERT mock, LLM reranker, GPT-style QA, RAG, CLIP/video mocks, rule agent, LangGraph-style mock, ranking/recommendation/prediction).
3. **Experiments:** same input across systems, seed/reproducibility hooks, JSONL logging.
4. **Evaluation:** domain-agnostic metrics when applicable (Recall@k, MRR, nDCG@k, accuracy-style checks) + local “LLM judge” proxy dimensions + pairwise forced choice.
5. **Insights:** research-style reasoning (best system, why, failures, hypothesis status, next steps)—not a shallow summary.
6. **Memory:** SQLite persistence for failures, experiment logs, performance history, hypothesis mapping, insights.

---

## 3. Key design decisions (what we iterated toward)

### 3.1 One interface to rule them all

We standardized on:

- `AISystem.run(self, input: dict) -> SystemOutput`
- `SystemOutput` carries `payload`, optional `ranked_ids`, `scores`, `raw_text`, `extras`

This made the **experiment engine** trivially system-agnostic: it only schedules `run()` and logs results.

### 3.2 “Local-first” evaluation without SaaS lock-in

We implemented:

- Classical IR metrics when `relevant_ids` exist
- A **local judge** using lexical signals (explicitly not an API product dependency)
- Pairwise comparisons derived from aggregated judge dimensions

This preserves a credible story for **enterprise-sensitive** workflows while leaving room to swap in a real model judge later.

### 3.3 Insight layer is not “pretty printing”

The insight engine composes:

- a composite score mixing IR metrics (when present) and judge signals
- explicit ranking + “next experiment” guidance
- failure hooks (execution failures vs quality failures)

We tuned failure detection so **retrieval-heavy outputs** don’t get misclassified as “hallucinations” without a reference answer.

### 3.4 Memory is the product’s long-term edge

SQLite tables capture experiments, evaluations, insights, failure cases, performance history, and hypothesis rows—so the system can accumulate **institutional research memory** instead of losing learnings in notebooks.

---

## 4. What shipped (high-level file map)

```text
research_os/
├── problem_compiler/
├── system_registry/
│   └── systems/          # IR, LLM, multimodal, agent, business implementations
├── experiment_engine/
├── evaluation_engine/
├── insight_engine/
├── memory/
├── ui/                   # Streamlit dashboard
├── data/
├── main.py               # CLI end-to-end demo
├── requirements.txt
└── README.md
```

---

## 5. “Session story” highlights (what a reviewer should take away)

1. **Speed:** a working vertical slice (compile → run → evaluate → insight → persist) shipped in a single agent-driven build pass, then refined with small correctness/UX fixes (README, assets, judge heuristics).
2. **Systems thinking:** the hard part wasn’t individual algorithms—it was **forcing heterogeneous systems into one contract** without collapsing domains into a fake generic UI.
3. **Operator-first UX:** Streamlit is intentionally “fast iteration, not production UX,” matching the stated user persona.
4. **Honest scope:** mocks (ColBERT, CLIP-like, video-like, LangGraph-like) are explicit placeholders behind the same interface—showing extensibility without pretending completeness.

---

## 6. How to verify quickly (commands)

From the parent directory of the `research_os` package (or from inside the repo root, depending on layout):

```bash
pip install -r research_os/requirements.txt   # or: pip install -r requirements.txt
python research_os/main.py --systems BM25Retriever DenseRetriever HybridRetriever
# or:
streamlit run research_os/ui/app.py
```

---

## 7. What we’d build next with more time (roadmap hints)

- Dataset/golden-set loaders and standardized “task bundles” per domain
- Pluggable remote judges / local LLM backends behind the same evaluation API
- Connectors (vector DBs, model providers) with explicit privacy modes
- Team workflows (roles, audit trails) once single-user loop is proven with design partners

---

## 8. Note on authenticity

This document is a **structured export** of the coding-agent collaboration that produced the repository, suitable for YC’s optional attachment. It is not a byte-for-byte dump of UI transcripts; it reflects the actual architecture and shipped modules in the codebase.
