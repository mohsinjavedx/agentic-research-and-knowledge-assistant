import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.schemas.research import (
    ResearchGraphState,
    ResearchReport,
    ResearchRequest,
    ResearchStatus,
    ResearchStepStatus,
    ResearchToolCall,
)
from app.schemas.retrieval import SearchResult
from app.services.research.graph import ResearchNodeTimeout, build_research_graph
from app.services.research.state import initial_research_state

ROOT = Path(__file__).resolve().parents[4]
GOLDEN_SET = ROOT / "data" / "eval" / "golden_set.json"
DOC_IDS = [
    UUID("35d86749-bf13-55ac-8008-231937b43bab"),
    UUID("a0fba681-ef99-5f3b-aee3-91ea98269e33"),
]
EVIDENCE = SearchResult(
    chunk_id=UUID("d6952626-7ccf-5543-8664-64a42c651c6e"),
    document_id=DOC_IDS[0],
    page_number=1,
    chunk_index=0,
    text="A verified example passage.",
    cosine_similarity=0.9,
)


class FakeOperations:
    def __init__(
        self,
        *,
        sufficient_after: int | None,
        tool_calls_per_round: int = 1,
        slow_node: str | None = None,
    ) -> None:
        self.sufficient_after = sufficient_after
        self.tool_calls_per_round = tool_calls_per_round
        self.slow_node = slow_node
        self.retrieve_count = 0

    async def _delay_if_slow(self, node: str) -> None:
        if self.slow_node == node:
            await asyncio.sleep(0.05)

    async def plan(self, state: ResearchGraphState) -> list[str]:
        await self._delay_if_slow("plan")
        return [state["query"]]

    async def execute_tools(
        self, state: ResearchGraphState, *, remaining_tool_calls: int
    ) -> tuple[list[SearchResult], list[ResearchToolCall]]:
        calls = [
            ResearchToolCall(
                name="search_documents",
                arguments={"query": state["query"]},
                status=ResearchStepStatus.COMPLETED,
                result_summary="Retrieved one evidence item.",
            )
            for _ in range(self.tool_calls_per_round)
        ]
        return [EVIDENCE], calls[:remaining_tool_calls]

    async def assess_sufficiency(self, state: ResearchGraphState) -> bool:
        await self._delay_if_slow("assess_sufficiency")
        return self.sufficient_after is not None and state["iterations"] >= self.sufficient_after

    async def retrieve_more(self, state: ResearchGraphState) -> list[SearchResult]:
        self.retrieve_count += 1
        return [EVIDENCE]

    async def synthesize(self, state: ResearchGraphState) -> ResearchReport:
        await self._delay_if_slow("synthesize")
        return ResearchReport(title="Research", summary=state["query"])

    async def verify_citations(
        self, report: ResearchReport, state: ResearchGraphState
    ) -> ResearchReport:
        await self._delay_if_slow("verify_citations")
        return report


def _initial_state(query: str) -> ResearchGraphState:
    request = ResearchRequest(query=query, document_ids=DOC_IDS)
    return initial_research_state(request, session_id=uuid4(), allowed_doc_ids=DOC_IDS)


@pytest.mark.parametrize(
    "question",
    [item["question"] for item in json.loads(GOLDEN_SET.read_text(encoding="utf-8"))["questions"]],
)
def test_graph_runs_plan_retrieve_assess_synthesize_and_verify(question: str) -> None:
    operations = FakeOperations(sufficient_after=2)
    graph = build_research_graph(operations)

    result = asyncio.run(graph.ainvoke(_initial_state(question)))

    assert result["status"] is ResearchStatus.COMPLETED
    assert result["iterations"] == 2
    assert result["tool_calls_count"] == 2
    assert len(result["tool_calls"]) == 2
    assert result["retrieved_evidence"] == [EVIDENCE]
    assert result["final_report"].summary == question
    assert [step.name for step in result["steps"]] == [
        "plan",
        "execute_tools",
        "assess_sufficiency",
        "retrieve_more",
        "execute_tools",
        "assess_sufficiency",
        "synthesize",
        "verify_citations",
    ]
    assert operations.retrieve_count == 1


def test_graph_synthesizes_partial_report_at_iteration_limit() -> None:
    operations = FakeOperations(sufficient_after=None)
    graph = build_research_graph(operations)

    result = asyncio.run(graph.ainvoke(_initial_state("Compare two papers")))

    assert result["iterations"] == 4
    assert result["tool_calls_count"] == 4
    assert operations.retrieve_count == 3
    assert result["final_report"].partial_coverage is True
    assert "execution budget" in result["final_report"].disclaimer


def test_graph_stops_adding_tools_at_tool_call_limit() -> None:
    operations = FakeOperations(sufficient_after=None, tool_calls_per_round=2)
    graph = build_research_graph(operations)

    result = asyncio.run(graph.ainvoke(_initial_state("Compare two papers")))

    assert result["iterations"] == 3
    assert result["tool_calls_count"] == 6
    assert operations.retrieve_count == 2
    assert result["final_report"].partial_coverage is True


@pytest.mark.parametrize("node", ["plan", "assess_sufficiency", "synthesize", "verify_citations"])
def test_each_llm_node_has_a_timeout(node: str) -> None:
    operations = FakeOperations(sufficient_after=1, slow_node=node)
    graph = build_research_graph(operations, llm_timeout_seconds=0.005)

    with pytest.raises(ResearchNodeTimeout) as error:
        asyncio.run(graph.ainvoke(_initial_state("Compare two papers")))

    assert error.value.node_name == node
    assert error.value.error_code == "RESEARCH_NODE_TIMEOUT"
