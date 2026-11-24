"""Pinned, redacted gitleaks scans of full Git history and the production bundle.

Run with Python 3.12+ from any directory. Tool/reports live in ignored tmp/.
No baseline or inline allow-comments. Framework exceptions are constrained by
path, field and key shape, and tested against provider injection/client leakage.
"""

import argparse
import base64
import hashlib
import io
import json
import os
import platform
import secrets
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "8.30.1"
RELEASE = f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}"
ASSETS = {
    "Windows": (
        "windows_x64.zip",
        "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
    ),
    "Linux": (
        "linux_x64.tar.gz",
        "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
    ),
}


def install_tool(directory: Path) -> Path:
    if (
        platform.machine().lower() not in {"amd64", "x86_64"}
        or platform.system() not in ASSETS
    ):
        raise RuntimeError("This pinned installer supports Windows/Linux x64.")
    suffix, checksum = ASSETS[platform.system()]
    asset = f"gitleaks_{VERSION}_{suffix}"
    executable = "gitleaks.exe" if os.name == "nt" else "gitleaks"
    # Revalidate the downloaded archive on every run, including cached installs.
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / asset
    if not archive.is_file():
        request = urllib.request.Request(
            f"{RELEASE}/{asset}", headers={"User-Agent": "phase8-scan"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(64 * 1024 * 1024 + 1)
        if len(data) > 64 * 1024 * 1024:
            raise RuntimeError("Scanner release exceeds the download bound.")
        archive.write_bytes(data)
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != checksum:
        raise RuntimeError("Scanner release checksum mismatch.")
    target = directory / executable
    # Extract only the expected regular binary; never unpack archive paths.
    if suffix.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            binary = bundle.read(executable)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as bundle:
            member = bundle.getmember(executable)
            if not member.isfile():
                raise RuntimeError("Scanner binary is not a regular archive member.")
            stream = bundle.extractfile(member)
            if stream is None:
                raise RuntimeError("Scanner binary is missing.")
            binary = stream.read()
    target.write_bytes(binary)
    if os.name != "nt":
        target.chmod(0o700)
    return target


def scan(tool: Path, mode: str, target: Path, report: Path) -> dict[str, object]:
    command = [
        str(tool),
        mode,
        str(target),
        "--redact=100",
        "--no-banner",
        "--no-color",
        "--report-format=json",
        f"--report-path={report}",
        "--ignore-gitleaks-allow",
        f"--config={ROOT / 'scripts' / 'gitleaks.toml'}",
        f"--gitleaks-ignore-path={report.parent / 'empty-ignore'}",
        "--timeout=300",
    ]
    if mode == "git":
        command.append("--log-opts=--all")
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, timeout=330, check=False
    )
    if result.returncode not in (0, 1) or not report.is_file():
        # Captured scanner output is deliberately not printed on an error path.
        raise RuntimeError("Scanner execution failed; no clean result is claimed.")
    findings = json.loads(report.read_text(encoding="utf-8")) or []
    if not isinstance(findings, list) or (result.returncode == 0) != (not findings):
        raise RuntimeError("Scanner exit status and report disagree.")
    return {
        "scope": mode,
        "target": str(target.relative_to(ROOT))
        if target.is_relative_to(ROOT)
        else "synthetic-fixture",
        "findings": len(findings),
        "locations": [
            {
                key: row.get(key)
                for key in ("RuleID", "File", "StartLine", "Commit", "Fingerprint")
            }
            for row in findings
        ],
    }


def require_full_history(root: Path) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Cannot determine repository history completeness.")
    if result.stdout.strip() != "false":
        raise RuntimeError(
            "Shallow history cannot satisfy the full-history gate; fetch full history."
        )


def verify_detector(tool: Path, output: Path) -> None:
    """Exceptions must never hide provider keys or any client-side key copy."""
    with tempfile.TemporaryDirectory(prefix="research-scanner-") as folder:
        fixture = Path(folder)
        (fixture / "canary.txt").write_text(
            "ghp_" + secrets.token_hex(18), encoding="utf-8"
        )
        if scan(tool, "dir", fixture, output / "canary-redacted.json")["findings"] != 1:
            raise RuntimeError("Synthetic secret detector check did not pass.")
        server = fixture / ".next" / "server"
        server.mkdir(parents=True)
        key = secrets.token_hex(32)
        (server / "preview-props.json").write_text(
            json.dumps({"previewModeSigningKey": key}), encoding="utf-8"
        )
        (server / "server-reference-manifest.json").write_text(
            json.dumps(
                {"encryptionKey": base64.b64encode(secrets.token_bytes(32)).decode()}
            ),
            encoding="utf-8",
        )
        cache = fixture / ".next" / "cache"
        cache.mkdir()
        (cache / ".rscinfo").write_text(
            json.dumps(
                {"encryption.key": base64.b64encode(secrets.token_bytes(32)).decode()}
            ),
            encoding="utf-8",
        )
        if (
            scan(tool, "dir", fixture, output / "framework-redacted.json")["findings"]
            != 1
        ):
            raise RuntimeError("Framework-only field policy did not pass.")
        (server / "preview-props.json").write_text(
            json.dumps(
                {
                    "previewModeSigningKey": key,
                    "provider_api_key": "ghp_" + secrets.token_hex(18),
                }
            ),
            encoding="utf-8",
        )
        if (
            scan(tool, "dir", fixture, output / "injected-redacted.json")["findings"]
            != 2
        ):
            raise RuntimeError("A provider token in a framework manifest was hidden.")
        public = fixture / ".next" / "static"
        public.mkdir()
        (public / "client.js").write_text(
            'previewModeSigningKey="' + key + '"', encoding="utf-8"
        )
        if (
            scan(tool, "dir", fixture, output / "client-canary-redacted.json")[
                "findings"
            ]
            != 3
        ):
            raise RuntimeError("A key copied to a client asset was hidden.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history-only", action="store_true", help="Bundle gate remains unverified"
    )
    arguments = parser.parse_args()
    require_full_history(ROOT)
    output = ROOT / "tmp" / "security"
    output.mkdir(parents=True, exist_ok=True)
    (output / "empty-ignore").write_text("", encoding="utf-8")
    tool = install_tool(output / "tools")
    verify_detector(tool, output)
    results = [scan(tool, "git", ROOT, output / "history-redacted.json")]
    if not arguments.history_only:
        bundle = ROOT / "apps" / "web" / ".next"
        if not (bundle / "BUILD_ID").is_file():
            raise RuntimeError("Build the production frontend before the bundle scan.")
        results.append(scan(tool, "dir", bundle, output / "bundle-redacted.json"))
    summary = {
        "tool": "gitleaks",
        "version": VERSION,
        "checksum_verified": True,
        "canary_detected": True,
        "manifest_injection_and_client_copy_detected": True,
        "full_acceptance_scan": not arguments.history_only,
        "results": results,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 1 if any(row["findings"] for row in results) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as exc:
        # No third-party exception text, request headers, or secret values.
        print(
            json.dumps({"status": "scanner_failed", "error_type": type(exc).__name__})
        )
        raise SystemExit(2) from None
