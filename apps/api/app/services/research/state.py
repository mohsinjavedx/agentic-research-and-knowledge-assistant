"""Typed initial state for a bounded research graph."""

from uuid import UUID

from app.schemas.research import ResearchGraphState, ResearchRequest, ResearchStatus


def initial_research_state(
    request: ResearchRequest, *, session_id: UUID, allowed_doc_ids: list[UUID]
) -> ResearchGraphState:
    if len(allowed_doc_ids) < 2:
        raise ValueError("Research requires at least two visible documents.")
    if len(allowed_doc_ids) != len(set(allowed_doc_ids)):
        raise ValueError("Allowed document IDs must be unique.")
    if not set(request.document_ids).issubset(allowed_doc_ids):
        raise ValueError("Requested documents must be included in the visible document scope.")
    return {
        "query": request.query,
        "session_id": session_id,
        "allowed_doc_ids": allowed_doc_ids,
        "top_k": request.top_k,
        "subquestions": [],
        "retrieved_evidence": [],
        "tool_calls": [],
        "tool_calls_count": 0,
        "iterations": 0,
        "sufficiency_verdict": None,
        "final_report": None,
        "status": ResearchStatus.QUEUED,
        "steps": [],
        "error_code": None,
    }
