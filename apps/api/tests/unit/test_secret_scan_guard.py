import importlib.util
import json
import os
import secrets
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_scanner_refuses_to_certify_shallow_history(monkeypatch):
    source = Path(__file__).resolve().parents[4] / "scripts" / "scan_secrets.py"
    spec = importlib.util.spec_from_file_location("phase8_scan_secrets", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="true\n"),
    )
    with pytest.raises(RuntimeError, match="Shallow"):
        module.require_full_history(Path.cwd())


def test_next_manifest_policy_is_field_and_path_specific(tmp_path):
    root = Path(__file__).resolve().parents[4]
    tool = root / "tmp/security/tools" / ("gitleaks.exe" if os.name == "nt" else "gitleaks")
    if not tool.exists():
        pytest.skip("The scanner's own CI self-test installs and exercises this policy")
    spec = importlib.util.spec_from_file_location(
        "phase8_scan_policy", root / "scripts/scan_secrets.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = tmp_path / "fixture"
    server = fixture / ".next/server"
    server.mkdir(parents=True)
    key = secrets.token_hex(32)
    (server / "preview-props.json").write_text(json.dumps({"previewModeSigningKey": key}))
    result = module.scan(tool, "dir", fixture, tmp_path / "report.json")
    assert result["findings"] == 0
    (server / "preview-props.json").write_text(
        json.dumps(
            {"previewModeSigningKey": key, "provider_api_key": "ghp_" + secrets.token_hex(18)}
        )
    )
    assert module.scan(tool, "dir", fixture, tmp_path / "report2.json")["findings"] == 1
    public = fixture / ".next/static"
    public.mkdir()
    (public / "client.js").write_text('previewModeSigningKey="' + key + '"')
    assert module.scan(tool, "dir", fixture, tmp_path / "report3.json")["findings"] == 2
