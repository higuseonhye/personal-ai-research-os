"""
Legacy CLI entrypoint (kept for backwards compatibility).

Runs the original pipeline:
problem → compile → experiment → evaluate → insight → memory
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evaluation_engine import evaluate_record
from experiment_engine import ExperimentEngine
from insight_engine import InsightEngine
from memory import ResearchMemory
from problem_compiler import ProblemCompiler
from system_registry import get_default_registry


def _default_ir_input() -> dict:
    return {
        "query": "enterprise security policy for remote access",
        "corpus": [
            {"id": "d1", "text": "Remote access must use VPN and MFA per enterprise security policy."},
            {"id": "d2", "text": "Office snacks are stored in the kitchen fridge."},
            {"id": "d3", "text": "Access reviews are quarterly for privileged accounts."},
        ],
        "relevant_ids": ["d1", "d3"],
        "top_k": 5,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal AI Research OS — legacy demo pipeline")
    parser.add_argument("problem", nargs="?", default="Search results are not accurate for enterprise documents")
    parser.add_argument("--systems", nargs="*", default=["BM25Retriever", "DenseRetriever", "HybridRetriever"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--input-json", type=str, default="", help="Path to JSON experiment input (IR-style)")
    args = parser.parse_args()

    compiler = ProblemCompiler()
    task = compiler.compile(args.problem)
    print(json.dumps(task.to_dict(), indent=2, ensure_ascii=False))

    reg = get_default_registry()
    engine = ExperimentEngine(reg)
    inp = _default_ir_input()
    if args.input_json:
        inp = json.loads(Path(args.input_json).read_text(encoding="utf-8"))

    record = engine.run_single(args.systems, inp, seed=args.seed)
    bundle = evaluate_record(record, inp, k=int(inp.get("top_k", 10)))
    insight_engine = InsightEngine()
    report = insight_engine.generate(task, record, bundle, input_snapshot=inp)

    mem = ResearchMemory()
    mem.persist_run(task, record, bundle, report)

    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

