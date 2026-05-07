"""
AI Solution Design OS — CLI entry (same backend as Streamlit hub).

Pipeline: Requirement → Structuring → Research → Methods → Composition
→ Execution Plan → Evaluation → Memory
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.design_os_pipeline import run_design_os
from core.design_os_present import print_cli_report


def main() -> None:
    demo = "Build internal document QA system with high accuracy under noisy data"
    text = demo if len(sys.argv) <= 1 else " ".join(sys.argv[1:])
    bundle = run_design_os(text, persist_memory=True)
    print_cli_report(bundle)


if __name__ == "__main__":
    main()
