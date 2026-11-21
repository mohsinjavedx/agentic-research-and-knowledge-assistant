import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location(
    "retrieval_runner", ROOT / "scripts/run_retrieval_eval.py"
)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_cli_refuses_to_overwrite_a_report_before_database_access(tmp_path: Path) -> None:
    output = tmp_path / "baseline.json"
    output.write_text("original baseline", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        runner.main(["--output", str(output)])
    assert caught.value.code == 2
    assert output.read_text(encoding="utf-8") == "original baseline"


def test_explicit_dataset_is_validated_instead_of_silently_using_default(tmp_path: Path) -> None:
    dataset = json.loads((ROOT / "data/eval/golden_set.json").read_text(encoding="utf-8"))
    dataset["questions"][0]["ground_truth"][0]["page_number"] = 999
    path = tmp_path / "invalid-labels.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid page"):
        runner._read_inputs(path)
