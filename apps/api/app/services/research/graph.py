"""LangGraph topology for bounded, multi-document research."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.schemas.research import (
    ResearchGraphState,
    ResearchReport,
    ResearchStatus,
    ResearchStep,
    ResearchStepStatus,
    ResearchToolCall,
)
from app.schemas.retrieval import SearchResult

type ResearchStepCallback = Callable[[ResearchStep], Awaitable[None]]

MAX_RESEARCH_ITERATIONS = 4
MAX_RESEARCH_TOOL_CALLS = 6


class ResearchGraphOperations(Protocol):
    async def plan(self, state: ResearchGraphState) -> list[str]: ...

    async def execute_tools(
        self, state: ResearchGraphState, *, remaining_tool_calls: int
    ) -> tuple[Sequence[SearchResult], Sequence[ResearchToolCall]]: ...

    async def assess_sufficiency(self, state: ResearchGraphState) -> bool: ...

    async def retrieve_more(self, state: ResearchGraphState) -> Sequence[SearchResult]: ...

    async def synthesize(self, state: ResearchGraphState) -> ResearchReport: ...

    async def verify_citations(
        self, report: ResearchReport, state: ResearchGraphState
    ) -> ResearchReport: ...


class ResearchNodeTimeout(TimeoutError):
    error_code = "RESEARCH_NODE_TIMEOUT"

    def __init__(self, node_name: str) -> None:
        self.node_name = node_name
        super().__init__(f"Research node timed out: {node_name}")


class ResearchBudgetExceeded(RuntimeError):
    error_code = "RESEARCH_TOOL_BUDGET_EXCEEDED"


def _merge_evidence(
    existing: Sequence[SearchResult], incoming: Sequence[SearchResult]
) -> list[SearchResult]:
    merged = list(existing)
    known_ids = {item.chunk_id for item in existing}
    for item in incoming:
        if item.chunk_id not in known_ids:
            merged.append(item)
            known_ids.add(item.chunk_id)
    return merged


def build_research_graph(
    operations: ResearchGraphOperations,
    *,
    llm_timeout_seconds: float = 90,
    max_iterations: int = MAX_RESEARCH_ITERATIONS,
    max_tool_calls: int = MAX_RESEARCH_TOOL_CALLS,
    on_step: ResearchStepCallback | None = None,
) -> CompiledStateGraph[ResearchGraphState, None, ResearchGraphState, ResearchGraphState]:
    """Build the workflow using injected operations for deterministic testing."""
    if (
        llm_timeout_seconds <= 0
        or not 1 <= max_iterations <= MAX_RESEARCH_ITERATIONS
        or not 1 <= max_tool_calls <= MAX_RESEARCH_TOOL_CALLS
    ):
        raise ValueError("Invalid research graph execution limits.")

    async def run_llm_node[T](node_name: str, operation: Callable[[], Awaitable[T]]) -> T:
        try:
            async with asyncio.timeout(llm_timeout_seconds):
                return await operation()
        except TimeoutError:
            raise ResearchNodeTimeout(node_name) from None

    async def record_step(
        state: ResearchGraphState,
        name: str,
        message: str,
        *,
        iterations: int | None = None,
        tool_calls_count: int | None = None,
    ) -> list[ResearchStep]:
        step = ResearchStep(
            name=name,
            status=ResearchStepStatus.COMPLETED,
            message=message,
            iteration=state["iterations"] if iterations is None else iterations,
            tool_calls_count=(
                state["tool_calls_count"] if tool_calls_count is None else tool_calls_count
            ),
        )
        if on_step is not None:
            await on_step(step)
        return [*state["steps"], step]

    async def plan(state: ResearchGraphState) -> dict[str, object]:
        subquestions = await run_llm_node("plan", lambda: operations.plan(state))
        return {
            "subquestions": subquestions,
            "status": ResearchStatus.RUNNING,
            "steps": await record_step(
                state, "plan", f"Planned {len(subquestions)} research question(s)."
            ),
        }

    async def execute_tools(state: ResearchGraphState) -> dict[str, object]:
        remaining_tool_calls = max_tool_calls - state["tool_calls_count"]
        if remaining_tool_calls <= 0:
            raise ResearchBudgetExceeded()
        evidence, calls = await operations.execute_tools(
            state, remaining_tool_calls=remaining_tool_calls
        )
        if len(calls) > remaining_tool_calls:
            raise ResearchBudgetExceeded()
        all_calls = [*state["tool_calls"], *calls]
        total_calls = state["tool_calls_count"] + len(calls)
        return {
            "retrieved_evidence": _merge_evidence(state["retrieved_evidence"], evidence),
            "tool_calls": all_calls,
            "tool_calls_count": total_calls,
            "iterations": state["iterations"] + 1,
            "steps": await record_step(
                state,
                "execute_tools",
                f"Executed {len(calls)} tool call(s).",
                iterations=state["iterations"] + 1,
                tool_calls_count=total_calls,
            ),
        }

    async def assess(state: ResearchGraphState) -> dict[str, object]:
        sufficient = await run_llm_node(
            "assess_sufficiency", lambda: operations.assess_sufficiency(state)
        )
        return {
            "sufficiency_verdict": sufficient,
            "steps": await record_step(
                state,
                "assess_sufficiency",
                "Evidence is sufficient." if sufficient else "More evidence may be needed.",
            ),
        }

    async def retrieve_more(state: ResearchGraphState) -> dict[str, object]:
        evidence = await operations.retrieve_more(state)
        return {
            "retrieved_evidence": _merge_evidence(state["retrieved_evidence"], evidence),
            "steps": await record_step(
                state, "retrieve_more", f"Added {len(evidence)} evidence item(s)."
            ),
        }

    async def synthesize(state: ResearchGraphState) -> dict[str, object]:
        report = await run_llm_node("synthesize", lambda: operations.synthesize(state))
        disclaimer = report.disclaimer
        if not state["sufficiency_verdict"] and (
            state["iterations"] >= max_iterations or state["tool_calls_count"] >= max_tool_calls
        ):
            report = report.model_copy(
                update={
                    "partial_coverage": True,
                    "disclaimer": disclaimer
                    or (
                        "The workflow reached its execution budget; "
                        "this report may have partial coverage."
                    ),
                }
            )
        return {
            "final_report": report,
            "status": state["status"],
            "steps": await record_step(state, "synthesize", "Created the research report."),
        }

    async def verify(state: ResearchGraphState) -> dict[str, object]:
        report = state["final_report"]
        if report is None:
            raise RuntimeError("The research graph reached citation verification without a report.")
        verified = await run_llm_node(
            "verify_citations", lambda: operations.verify_citations(report, state)
        )
        return {
            "final_report": verified,
            "status": ResearchStatus.COMPLETED,
            "steps": await record_step(state, "verify_citations", "Verified report citations."),
        }

    def route_after_assessment(state: ResearchGraphState) -> str:
        if state["sufficiency_verdict"]:
            return "synthesize"
        if state["iterations"] < max_iterations and state["tool_calls_count"] < max_tool_calls:
            return "retrieve_more"
        return "synthesize"

    graph = StateGraph(ResearchGraphState)
    graph.add_node("plan", plan)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("assess_sufficiency", assess)
    graph.add_node("retrieve_more", retrieve_more)
    graph.add_node("synthesize", synthesize)
    graph.add_node("verify_citations", verify)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "execute_tools")
    graph.add_edge("execute_tools", "assess_sufficiency")
    graph.add_conditional_edges(
        "assess_sufficiency",
        route_after_assessment,
        {"retrieve_more": "retrieve_more", "synthesize": "synthesize"},
    )
    graph.add_edge("retrieve_more", "execute_tools")
    graph.add_edge("synthesize", "verify_citations")
    graph.add_edge("verify_citations", END)
    return graph.compile()
