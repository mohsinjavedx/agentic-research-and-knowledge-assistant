import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location(
    "phase5_runner", ROOT / "scripts/run_phase5_ablation.py"
)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def variant(recall=0.77, mrr=0.62, exact_recall=0.7, exact_mrr=0.6, memory=10_000_000):
    return {
        "metrics": {"recall@5": recall, "mrr": mrr},
        "exact_match_metrics": {"recall@5": exact_recall, "mrr": exact_mrr},
        "sql_p95_ms": 100,
        "incremental_worker_rss_bytes": memory,
        "available": True,
    }


def test_gates_use_percentage_points_and_enforce_recall_regression() -> None:
    baseline = variant()
    assert not runner.check_gates(baseline, variant(mrr=0.669))["passed"]
    assert runner.check_gates(baseline, variant(mrr=0.67))["passed"]
    assert runner.check_gates(baseline, variant(exact_mrr=0.75))["passed"]
    assert not runner.check_gates(baseline, variant(recall=0.75, mrr=0.8))["passed"]


@pytest.mark.parametrize("memory", [None, 50_000_000, 50_000_001])
def test_memory_budget_is_strict_and_unmeasured_is_not_a_pass(memory) -> None:
    assert not runner.check_gates(variant(), variant(mrr=0.7, memory=memory))["passed"]


def test_failed_reranker_or_missing_sql_measurement_cannot_pass() -> None:
    missing = variant(mrr=0.8)
    missing["available"] = False
    assert not runner.check_gates(variant(), missing)["passed"]
    missing = variant(mrr=0.8)
    missing["sql_p95_ms"] = 1201
    assert not runner.check_gates(variant(), missing)["passed"]
    missing = variant(mrr=0.8)
    missing["sql_p95_ms"] = None
    assert not runner.check_gates(variant(), missing)["passed"]


def test_summary_scores_ranked_cores_and_ignores_added_context() -> None:
    queries = [
        {
            "id": "one",
            "answerable": True,
            "ground_truth": [{"document_id": "doc", "page_number": 7}],
            "results": [{"document_id": "doc", "page_number": 1}],
            "adjacent_context": [{"document_id": "doc", "page_number": 7}],
        }
    ]
    assert runner.summarize(queries)["recall@5"] == 0


def test_phase5_cli_preserves_reports_before_accessing_database(tmp_path) -> None:
    report = tmp_path / "report.json"
    report.write_text("preserved", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        runner.main(["--output", str(report)])
    assert caught.value.code == 2
    assert report.read_text(encoding="utf-8") == "preserved"
