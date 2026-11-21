import json
import runpy
from pathlib import Path
from typing import Any

import httpx
import pytest

RUNNER_PATH = Path(__file__).resolve().parents[4] / "scripts" / "run_grounded_qa_eval.py"
RUNNER = runpy.run_path(str(RUNNER_PATH))


def test_score_audit_rejects_incomplete_question_set(tmp_path: Path) -> None:
    questions: list[dict[str, Any]] = RUNNER["_read_questions"]()
    answers = [
        {
            "id": question["id"],
            "answerable": question["answerable"],
            "insufficient_evidence": True,
            "citations": [],
            "evidence": [],
        }
        for question in questions[:-1]
    ]
    report = {
        "version": 1,
        "answers": answers,
        "manual_claim_audit": [
            {"id": question["id"], "faithful": None}
            for question in questions
            if question["answerable"]
        ],
    }
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="all 40 correctly labelled questions"):
        RUNNER["_score_audit"](audit_path)


def test_live_evaluation_records_http_failures_and_continues_all_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path.endswith("/session"):
            return httpx.Response(204)
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"detail": "Unavailable"})
        return httpx.Response(
            200,
            json={
                "answer": "Insufficient evidence.",
                "citations": [],
                "evidence": [],
                "used_evidence": [],
                "degraded_mode": False,
                "insufficient_evidence": True,
            },
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(respond)),
    )
    report = RUNNER["_run_api"]("http://unit-test", 5)
    assert len(report["answers"]) == 40
    assert report["answers"][0]["status_code"] == 503
    assert report["answers"][0]["insufficient_evidence"] is False
    assert RUNNER["_acceptance"](report)["checks"]["request_success"]["passed"] is False


def test_evaluation_checks_quote_offsets_and_actual_used_context() -> None:
    chunk_id = "00000000-0000-0000-0000-000000000001"
    doc_id = "00000000-0000-0000-0000-000000000100"
    source = {
        "chunk_id": chunk_id,
        "document_id": doc_id,
        "page_number": 7,
        "text": "Alpha and Beta.",
    }
    used = {**source, "start": 0, "end": 15, "context_index": 0, "retrieval_index": 0}
    citation = {
        "chunk_id": chunk_id,
        "document_id": doc_id,
        "page_number": 7,
        "claim": "Alpha and Beta.",
        "quote": "Alpha and Beta.",
        "quote_start": 0,
        "quote_end": 15,
    }
    check = RUNNER["_citation_is_retrieved"]
    assert check(citation, [source], [used]) is True
    assert check({**citation, "quote": "Invented fact."}, [source], [used]) is False
    assert check(citation, [source], []) is False


@pytest.mark.parametrize("body", [b"not json", b"null", b"[]", b'{"answer":123}'])
def test_malformed_http_200_is_a_failed_row_without_aborting_the_run(
    body: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path.endswith("/session"):
            return httpx.Response(204)
        calls += 1
        if calls == 1:
            return httpx.Response(200, content=body)
        return httpx.Response(
            200,
            json={
                "answer": "Insufficient evidence.",
                "citations": [],
                "evidence": [],
                "used_evidence": [],
                "degraded_mode": False,
                "insufficient_evidence": True,
            },
        )

    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond))
    )
    report = RUNNER["_run_api"]("http://unit-test", 5)
    assert len(report["answers"]) == 40
    assert report["answers"][0]["error"]
    assert report["answers"][0]["insufficient_evidence"] is False
    assert RUNNER["_acceptance"](report)["checks"]["request_success"]["passed"] is False
