import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest
from pydantic import ValidationError

from app.core.config import load_settings
from app.db.session import Database
from app.providers.embeddings import BGETokenizer
from app.providers.identity import EmbeddingIdentity
from app.schemas.research import CompareSectionsArguments
from app.schemas.retrieval import SearchResult
from app.services.research.tools import (
    ResearchToolBudget,
    ResearchToolError,
    ResearchToolRegistry,
    ResearchTools,
    _outline_sections,
)
from app.services.retrieval.dense import RetrievedChunk

ROOT = Path(__file__).resolve().parents[4]
GOLDEN_SET = ROOT / "data" / "eval" / "golden_set.json"
DOC_IDS = [
    UUID("35d86749-bf13-55ac-8008-231937b43bab"),
    UUID("a0fba681-ef99-5f3b-aee3-91ea98269e33"),
]
CHUNK_ID = UUID("d6952626-7ccf-5543-8664-64a42c651c6e")


class FakeEmbeddingProvider:
    identity = EmbeddingIdentity()
    kind = "local"

    def __init__(self) -> None:
        self.tokenizer = BGETokenizer()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 383 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 383

    def close(self) -> None:
        pass


def _tools() -> ResearchTools:
    return ResearchTools(
        Database(load_settings()),
        FakeEmbeddingProvider(),  # type: ignore[arg-type]
        load_settings(),
        session_id=uuid4(),
        allowed_doc_ids=DOC_IDS,
    )


def _result(document_id: UUID) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid5(document_id, str(CHUNK_ID)),
        document_id=document_id,
        page_number=1,
        chunk_index=0,
        text="A verified evidence passage.",
        cosine_similarity=0.9,
    )


def test_outline_extracts_markdown_headings_and_uses_page_fallback() -> None:
    sections = _outline_sections(
        [
            (0, 1, "# Introduction\nSome text.\n## Methods\nDetails."),
            (1, 2, "Continued text."),
        ]
    )

    assert [(item.heading, item.page_number) for item in sections] == [
        ("Introduction", 1),
        ("Methods", 1),
    ]
    fallback = _outline_sections([(0, 3, "No markdown headings here.")])
    assert [(item.heading, item.page_number) for item in fallback] == [("Page 3", 3)]


@pytest.mark.parametrize(
    "question",
    [item["question"] for item in json.loads(GOLDEN_SET.read_text(encoding="utf-8"))["questions"]],
)
def test_search_tool_validates_scope_and_returns_golden_query_evidence(
    question: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _tools()
    scope_checks: list[list[UUID]] = []
    search_scopes: list[list[UUID]] = []

    async def visible(database, session_id, requested_ids):
        scope_checks.append(requested_ids)
        return requested_ids

    async def search(database, provider, query, allowed_doc_ids, *, top_k, mode):
        search_scopes.append(allowed_doc_ids)
        return [_result(identity) for identity in allowed_doc_ids]

    monkeypatch.setattr("app.services.research.tools.visible_document_ids", visible)
    monkeypatch.setattr("app.services.research.tools.search_evidence", search)
    registry = ResearchToolRegistry(tools)

    async def run() -> list[SearchResult]:
        return await registry.invoke(
            "search_documents",
            {"query": question, "doc_ids": [str(identity) for identity in DOC_IDS], "top_k": 5},
        )

    try:
        results = asyncio.run(run())
    finally:
        asyncio.run(tools.database.close())

    assert len(results) == 2
    assert {item.document_id for item in results} == set(DOC_IDS)
    assert scope_checks == [DOC_IDS]
    assert search_scopes == [DOC_IDS]


def test_registry_rejects_unknown_tools_invalid_arguments_and_foreign_documents() -> None:
    tools = _tools()
    registry = ResearchToolRegistry(tools)

    async def run() -> None:
        with pytest.raises(ResearchToolError, match="TOOL_NOT_ALLOWED"):
            await registry.invoke("execute_python", {})
        with pytest.raises(ResearchToolError, match="INVALID_TOOL_ARGUMENTS"):
            await registry.invoke(
                "search_documents",
                {"query": "evidence", "doc_ids": [str(DOC_IDS[0])], "top_k": 0},
            )
        with pytest.raises(ResearchToolError, match="DOCUMENT_OUTSIDE_RESEARCH_SCOPE"):
            await registry.invoke("get_document_outline", {"doc_id": str(uuid4())})

    try:
        asyncio.run(run())
    finally:
        asyncio.run(tools.database.close())


def test_comparison_arguments_require_two_distinct_documents() -> None:
    with pytest.raises(ValidationError, match="different documents"):
        CompareSectionsArguments(
            topic="methods",
            doc_a_id=DOC_IDS[0],
            doc_b_id=DOC_IDS[0],
        )


def test_concurrent_tool_calls_cannot_exceed_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = _tools()

    async def visible(database, session_id, requested_ids):
        return requested_ids

    async def search(database, provider, query, allowed_doc_ids, *, top_k, mode):
        return [_result(identity) for identity in allowed_doc_ids]

    monkeypatch.setattr("app.services.research.tools.visible_document_ids", visible)
    monkeypatch.setattr("app.services.research.tools.search_evidence", search)
    budget = ResearchToolBudget(max_tool_calls=6)
    registry = ResearchToolRegistry(tools, budget)
    arguments = {
        "query": "evidence",
        "doc_ids": [str(identity) for identity in DOC_IDS],
        "top_k": 5,
    }

    async def run():
        return await asyncio.gather(
            *(registry.invoke("search_documents", arguments) for _ in range(7)),
            return_exceptions=True,
        )

    try:
        outcomes = asyncio.run(run())
    finally:
        asyncio.run(tools.database.close())

    successes = [outcome for outcome in outcomes if isinstance(outcome, list)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, ResearchToolError)]
    assert len(successes) == 6
    assert len(failures) == 1
    assert failures[0].error_code == "TOOL_CALL_LIMIT_REACHED"
    assert budget.tool_calls_count == 6
