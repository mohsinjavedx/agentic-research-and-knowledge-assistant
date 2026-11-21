"""Evaluate the Phase 4 answer API and create a 30-answer human-review packet."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_SET_PATH = REPOSITORY_ROOT / "data" / "eval" / "golden_set.json"
sys.path.insert(0, str(REPOSITORY_ROOT / "apps" / "api"))

from app.schemas.answers import AnswerResponse  # noqa: E402


def _read_questions() -> list[dict[str, Any]]:
    data = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    questions = data.get("questions")
    if data.get("version") != 1 or not isinstance(questions, list) or len(questions) != 40:
        raise ValueError("Phase 4 evaluation requires the version 1 40-question gold set.")
    if sum(item.get("answerable") is True for item in questions) != 30:
        raise ValueError("Phase 4 evaluation requires 30 answerable questions.")
    if sum(item.get("answerable") is False for item in questions) != 10:
        raise ValueError("Phase 4 evaluation requires 10 out-of-corpus questions.")
    return questions


def _citation_is_retrieved(
    citation: dict[str, Any], evidence: list[dict[str, Any]], used_evidence: list[dict[str, Any]]
) -> bool:
    try:
        chunk_id = UUID(citation["chunk_id"])
        document_id = UUID(citation["document_id"])
        page_number = citation["page_number"]
        start, end, quote = citation["quote_start"], citation["quote_end"], citation["quote"]
        if (
            type(start) is not int
            or type(end) is not int
            or not isinstance(quote, str)
            or not quote
        ):
            return False
    except (KeyError, TypeError, ValueError):
        return False
    for index, source in enumerate(evidence):
        if not (
            chunk_id == UUID(source["chunk_id"])
            and document_id == UUID(source["document_id"])
            and page_number == source["page_number"]
        ):
            continue
        if not 0 <= start < end <= len(source["text"]) or source["text"][start:end] != quote:
            return False
        return any(
            used.get("chunk_id") == str(chunk_id)
            and used.get("document_id") == str(document_id)
            and used.get("page_number") == page_number
            and used.get("retrieval_index") == index
            and type(used.get("start")) is int
            and type(used.get("end")) is int
            and 0 <= used["start"] <= start < end <= used["end"] <= len(source["text"])
            and source["text"][used["start"] : used["end"]] == used.get("text")
            for used in used_evidence
        )
    return False


def _request_succeeded(item: dict[str, Any]) -> bool:
    return (
        item.get("status_code") == 200
        and item.get("payload_valid") is True
        and not item.get("error")
        and item.get("degraded_mode") is False
    )


def _acceptance(report: dict[str, Any]) -> dict[str, Any]:
    citations = [
        (citation, item["evidence"], item.get("used_evidence", []), item.get("answer", ""))
        for item in report["answers"]
        for citation in item["citations"]
    ]
    valid_count = sum(
        _citation_is_retrieved(citation, evidence, used)
        and bool(citation.get("claim", "").strip())
        and " ".join(citation.get("claim", "").split()) in " ".join(answer.split())
        for citation, evidence, used, answer in citations
    )
    total_count = len(citations)
    unanswerable = [item for item in report["answers"] if not item["answerable"]]
    detected = sum(
        _request_succeeded(item) and item["insufficient_evidence"] for item in unanswerable
    )
    detection_rate = detected / len(unanswerable) if unanswerable else 0.0
    audit_items = report["manual_claim_audit"]
    reviewed = [item for item in audit_items if isinstance(item.get("faithful"), bool)]
    faithful = sum(item["faithful"] for item in reviewed)
    faithfulness_rate = faithful / len(reviewed) if reviewed else None
    claim_check_passed = (
        len(reviewed) == 30 and faithfulness_rate is not None and faithfulness_rate >= 0.9
    )
    checks = {
        "request_success": {
            "value": sum(_request_succeeded(item) for item in report["answers"])
            / len(report["answers"])
            if report["answers"]
            else 0.0,
            "target": 1.0,
            "passed": bool(report["answers"])
            and all(_request_succeeded(item) for item in report["answers"]),
        },
        "answerable_completion": {
            "answered": sum(
                item["answerable"]
                and _request_succeeded(item)
                and not item["insufficient_evidence"]
                and bool(item["citations"])
                for item in report["answers"]
            ),
            "total": sum(item["answerable"] for item in report["answers"]),
        },
        "citation_validity": {
            "value": valid_count / total_count if total_count else None,
            "valid": valid_count,
            "total": total_count,
            "target": 1.0,
            "passed": total_count > 0 and valid_count == total_count,
        },
        "abstention_accuracy": {
            "value": detection_rate,
            "detected": detected,
            "total": len(unanswerable),
            "target": 0.9,
            "passed": detection_rate >= 0.9,
        },
        "citation_claim_support_manual": {
            "value": faithfulness_rate,
            "faithful": faithful,
            "reviewed": len(reviewed),
            "total": len(audit_items),
            "target": 0.9,
            "passed": claim_check_passed if len(reviewed) == 30 else None,
        },
    }
    completion = checks["answerable_completion"]
    completion["value"] = (
        completion["answered"] / completion["total"] if completion["total"] else 0.0
    )
    completion["target"] = 0.9
    completion["passed"] = completion["value"] >= 0.9
    return {
        "checks": checks,
        "passed": all(check["passed"] is True for check in checks.values()),
    }


def _run_api(base_url: str, timeout: float) -> dict[str, Any]:
    questions = _read_questions()
    answers: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        session_response = client.post("/api/v1/session")
        if session_response.status_code != 204:
            raise RuntimeError(
                f"Could not create an API session (HTTP {session_response.status_code})."
            )
        for item in questions:
            started = perf_counter()
            status_code: int | None = None
            error: str | None = None
            server_timing: str | None = None
            payload_valid = False
            payload: dict[str, Any] = {}
            try:
                response = client.post(
                    "/api/v1/answer", json={"query": item["question"], "top_k": 5}
                )
                status_code = response.status_code
                server_timing = response.headers.get("server-timing")
                if status_code == 200:
                    validated = AnswerResponse.model_validate_json(response.content, strict=True)
                    payload = validated.model_dump(mode="json")
                    payload_valid = True
                else:
                    error = f"HTTP_{status_code}"
            except (httpx.HTTPError, ValueError) as exc:
                error = type(exc).__name__
            latency_ms = (perf_counter() - started) * 1000
            evidence = payload.get("evidence", [])
            citations = payload.get("citations", [])
            answers.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "answerable": item["answerable"],
                    "answer": payload.get("answer", ""),
                    "insufficient_evidence": payload.get("insufficient_evidence", False),
                    "degraded_mode": payload.get("degraded_mode", False),
                    "citations": citations,
                    "evidence": evidence,
                    "used_evidence": payload.get("used_evidence", []),
                    "status_code": status_code,
                    "payload_valid": payload_valid,
                    "error": error,
                    "latency_ms": latency_ms,
                    "server_timing": server_timing,
                }
            )
            print(
                json.dumps(
                    {
                        "id": item["id"],
                        "status": status_code,
                        "latency_ms": round(latency_ms, 2),
                        "citations": len(citations),
                        "insufficient_evidence": payload.get("insufficient_evidence", False),
                    }
                ),
                flush=True,
            )
    manual_audit = [
        {
            "id": item["id"],
            "question": item["question"],
            "answer": item["answer"],
            "citations": item["citations"],
            "evidence": item["evidence"],
            "used_evidence": item["used_evidence"],
            "status_code": item["status_code"],
            "faithful": None,
            "review_note": "",
        }
        for item in answers
        if item["answerable"]
    ]
    return {
        "version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_dataset": "data/eval/golden_set.json",
        "source_dataset_sha256": hashlib.sha256(GOLDEN_SET_PATH.read_bytes()).hexdigest(),
        "api_base_url": base_url,
        "answers": answers,
        "manual_claim_audit": manual_audit,
    }


def _score_audit(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    questions = _read_questions()
    expected_answers = {item["id"]: item["answerable"] for item in questions}
    answers = report.get("answers")
    if (
        report.get("version") not in {1, 2}
        or not isinstance(answers, list)
        or len(answers) != 40
        or any(not isinstance(item, dict) for item in answers)
        or any(not isinstance(item.get("id"), str) for item in answers)
        or {item.get("id") for item in answers} != set(expected_answers)
        or any(item.get("answerable") is not expected_answers[item["id"]] for item in answers)
    ):
        raise ValueError("The audit file must contain all 40 correctly labelled questions.")

    manual_audit = report.get("manual_claim_audit")
    answerable_ids = {
        question_id for question_id, answerable in expected_answers.items() if answerable
    }
    if (
        not isinstance(manual_audit, list)
        or len(manual_audit) != 30
        or any(not isinstance(item, dict) for item in manual_audit)
        or any(not isinstance(item.get("id"), str) for item in manual_audit)
        or {item.get("id") for item in manual_audit} != answerable_ids
    ):
        raise ValueError("The audit file must contain all 30 Phase 4 answerable questions.")
    report["acceptance"] = _acceptance(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--score-audit",
        type=Path,
        help="Score an existing review packet after marking all 30 faithful values true/false.",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation output: {args.output}")
    report = (
        _score_audit(args.score_audit)
        if args.score_audit
        else _run_api(args.base_url, args.timeout)
    )
    report["acceptance"] = _acceptance(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps(report["acceptance"], ensure_ascii=True, indent=2))
    print(f"Full report: {args.output}")
    return 0 if report["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
