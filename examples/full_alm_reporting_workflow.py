"""Manual-run script for the Full ALM reporting workflow.

Importing this module is a no-op. The workflow only runs when this file is
executed directly (`python examples/full_alm_reporting_workflow.py`).
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pk_alm.workflows.full_alm_workflow import (
    run_full_alm_reporting_workflow,
    summarize_generated_outputs,
)

DEFAULT_OUTPUT_DIR = Path("outputs/full_alm_scenario")


def main() -> None:
    result = run_full_alm_reporting_workflow(DEFAULT_OUTPUT_DIR)
    summary = summarize_generated_outputs(result)

    print("=== Full ALM Reporting Workflow ===")
    print(f"Output directory        : {summary['output_dir']}")
    print(f"Generation mode         : {summary['generation_mode']}")
    print("Generated CSV files:")
    for path in result.generated_files["csv"]:
        print(f"  - {path}")
    print("Generated PNG files:")
    for path in result.generated_files["png"]:
        print(f"  - {path}")
    benchmark_status = (
        result.benchmark_path if result.benchmark_path is not None else "not generated"
    )
    print(f"Benchmark file          : {benchmark_status}")
    print()
    print("Note: this example uses the required live AAL/ACTUS asset path.")


if __name__ == "__main__":
    main()
