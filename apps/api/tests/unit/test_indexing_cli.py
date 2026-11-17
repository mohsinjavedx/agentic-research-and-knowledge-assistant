import json
import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.services.indexing.cli", *arguments],
        cwd=API_ROOT,
        env={**os.environ, "HF_HUB_OFFLINE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_help_does_not_load_models_or_require_database() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "--persist" in result.stdout


def test_persist_requires_explicit_document_scope() -> None:
    result = run_cli("missing.pdf", "--persist")
    assert result.returncode == 2
    assert "--sample or --session-id" in result.stderr


def test_existing_export_is_not_overwritten_or_embedded(tmp_path: Path) -> None:
    target = tmp_path / "existing.json"
    target.write_text("keep me", encoding="utf-8")
    result = run_cli("missing.pdf", "--output", str(target))
    assert result.returncode == 1
    assert json.loads(result.stdout)["error_code"] == "OUTPUT_FILE_EXISTS"
    assert target.read_text() == "keep me"


def test_malformed_pdf_rejected_before_model_loading(tmp_path: Path) -> None:
    source = tmp_path / "invalid.pdf"
    source.write_bytes(b"%PDF-not-a-document")
    result = run_cli(str(source))
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "failed"
