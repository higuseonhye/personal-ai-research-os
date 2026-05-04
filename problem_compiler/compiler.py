from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

Domain = Literal["IR", "LLM", "Multimodal", "Agent", "Business"]


@dataclass
class StructuredResearchTask:
    """Structured output from the problem compiler."""

    task_type: str
    domain: Domain
    hypothesis: list[str]
    evaluation_focus: list[str]
    suggested_systems: list[str]
    raw_problem: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "domain": self.domain,
            "hypothesis": self.hypothesis,
            "evaluation_focus": self.evaluation_focus,
            "suggested_systems": self.suggested_systems,
            "raw_problem": self.raw_problem,
            "metadata": self.metadata,
        }


_RULES: list[tuple[re.Pattern[str], Domain, str, list[str], list[str], list[str]]] = [
    (
        re.compile(
            r"search|retriev|bm25|index|rank|recall|mrr|ndcg|enterprise\s+doc|document",
            re.I,
        ),
        "IR",
        "information_retrieval",
        [
            "Improving lexical or semantic matching will lift retrieval quality.",
            "Hybrid retrieval may outperform pure dense or sparse alone.",
        ],
        ["Recall@k", "MRR", "nDCG@k", "reranking gain", "latency"],
        ["BM25Retriever", "DenseRetriever", "HybridRetriever", "ColBERTRetriever", "LLMReranker"],
    ),
    (
        re.compile(
            r"answer|rag|qa|hallucin|ground|context|llm|gpt|prompt|generation",
            re.I,
        ),
        "LLM",
        "llm_qa_or_rag",
        [
            "Better grounding reduces hallucinations.",
            "RAG with strong retrieval improves factual QA.",
        ],
        ["correctness", "relevance", "hallucination risk", "usefulness"],
        ["GPTStyleQA", "RAGSystem"],
    ),
    (
        re.compile(
            r"video|multimodal|clip|twelvelabs|frame|visual|image|embedding\s+space",
            re.I,
        ),
        "Multimodal",
        "multimodal_retrieval_or_understanding",
        [
            "Cross-modal alignment quality drives retrieval accuracy.",
            "Temporal structure matters for long-form video.",
        ],
        ["cross-modal relevance", "temporal coherence", "judge scores"],
        ["CLIPRetrieval", "VideoRetrievalSystem"],
    ),
    (
        re.compile(
            r"agent|plan|tool|workflow|autonom|langgraph|orchestr",
            re.I,
        ),
        "Agent",
        "agentic_planning_or_tools",
        [
            "Decomposition quality affects end-task success.",
            "Tool selection errors dominate failure modes.",
        ],
        ["task success", "plan validity", "tool-use correctness"],
        ["RuleBasedAgent", "LangGraphStylePlanner"],
    ),
    (
        re.compile(
            r"rank|recommend|predict|conversion|churn|click|business|model\s+score",
            re.I,
        ),
        "Business",
        "business_ml_ranking_or_prediction",
        [
            "Feature representation shifts ranking calibration.",
            "Cold-start segments need separate handling.",
        ],
        ["Accuracy", "AUC proxy", "ranking quality", "calibration"],
        ["RankingModel", "RecommendationModel", "PredictionModel"],
    ),
]


class ProblemCompiler:
    """Convert raw customer/business problems into structured AI research tasks."""

    def compile(self, problem_description: str) -> StructuredResearchTask:
        text = (problem_description or "").strip()
        if not text:
            return StructuredResearchTask(
                task_type="unspecified",
                domain="LLM",
                hypothesis=["Define a sharper problem statement to target experiments."],
                evaluation_focus=["clarity", "measurable KPI"],
                suggested_systems=["GPTStyleQA", "RuleBasedAgent"],
                raw_problem=text,
                metadata={"note": "empty_input"},
            )

        for pattern, domain, task_type, hypo, focus, systems in _RULES:
            if pattern.search(text):
                return StructuredResearchTask(
                    task_type=task_type,
                    domain=domain,
                    hypothesis=list(hypo),
                    evaluation_focus=list(focus),
                    suggested_systems=list(systems),
                    raw_problem=text,
                    metadata={"matched_rule": pattern.pattern},
                )

        return StructuredResearchTask(
            task_type="general_ai_research",
            domain="LLM",
            hypothesis=[
                "A baseline LLM pipeline establishes a lower bound before specialized systems.",
            ],
            evaluation_focus=["relevance", "correctness", "usefulness", "hallucination risk"],
            suggested_systems=["GPTStyleQA", "RAGSystem", "DenseRetriever", "RuleBasedAgent"],
            raw_problem=text,
            metadata={"matched_rule": "default"},
        )
