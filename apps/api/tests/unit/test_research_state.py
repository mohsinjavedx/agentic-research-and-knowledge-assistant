import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.schemas.research import ResearchRequest, ResearchStatus
from app.services.research.state import initial_research_state

ROOT = Path(__file__).resolve().parents[4]
GOLDEN_SET = ROOT / "data" / "eval" / "golden_set.json"
SAMPLE_IDS = [
    UUID("35d86749-bf13-55ac-8008-231937b43bab"),
    UUID("a0fba681-ef99-5f3b-aee3-91ea98269e33"),
    UUID("be12ca47-9e95-56c9-abdc-104a9f7680f5"),
]


def test_typed_research_state_accepts_the_fixed_golden_queries() -> None:
    questions = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))["questions"]
    assert len(questions) == 40
    for item in questions:
        request = ResearchRequest(query=item["question"], document_ids=SAMPLE_IDS[:2], top_k=5)
        state = initial_research_state(request, session_id=uuid4(), allowed_doc_ids=SAMPLE_IDS)

        assert state["query"] == item["question"]
        assert state["allowed_doc_ids"] == SAMPLE_IDS
        assert state["subquestions"] == []
        assert state["retrieved_evidence"] == []
        assert state["tool_calls_count"] == 0
        assert state["iterations"] == 0
        assert state["sufficiency_verdict"] is None
        assert state["final_report"] is None
        assert state["status"] is ResearchStatus.QUEUED


def test_research_request_requires_distinct_multi_document_scope() -> None:
    with pytest.raises(ValidationError, match="unique"):
        ResearchRequest(query="Compare these papers", document_ids=[SAMPLE_IDS[0]] * 2)

    with pytest.raises(ValidationError):
        ResearchRequest(query=" ", document_ids=SAMPLE_IDS[:2])


def test_initial_state_rejects_documents_outside_the_visible_scope() -> None:
    request = ResearchRequest(
        query="Compare the studies", document_ids=[SAMPLE_IDS[0], SAMPLE_IDS[2]]
    )

    with pytest.raises(ValueError, match="visible document scope"):
        initial_research_state(request, session_id=uuid4(), allowed_doc_ids=SAMPLE_IDS[:2])
