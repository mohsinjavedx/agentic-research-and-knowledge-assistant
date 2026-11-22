"""Concrete research operations backed by existing retrieval and generation services."""

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from app.core.config import Settings
from app.db.session import Database
from app.providers.embeddings import EmbeddingProvider
from app.providers.llm import LLMProvider
from app.schemas.research import (
    ResearchComparison,
    ResearchGraphState,
    ResearchReport,
    ResearchRequest,
    ResearchSection,
    ResearchStepStatus,
    ResearchToolCall,
)
from app.schemas.retrieval import SearchResult
from app.services.generation.answer import INSUFFICIENT_ANSWER
from app.services.generation.citations import answer_is_covered, verify_citations
from app.services.research.graph import (
    ResearchStepCallback,
    build_research_graph,
)
from app.services.research.state import initial_research_state
from app.services.research.tools import (
    ResearchToolBudget,
    ResearchToolError,
    ResearchToolRegistry,
    ResearchTools,
)
from app.services.retrieval.dense import RetrievedChunk


class AgentResearchOperations:
    def __init__(
        self,
        registry: ResearchToolRegistry,
        llm_provider: LLMProvider,
        settings: Settings,
    ) -> None:
        self.registry = registry
        self.llm_provider = llm_provider
        self.settings = settings

    async def plan(self, state: ResearchGraphState) -> list[str]:
        return [state["query"]]

    async def _invoke(
        self,
        name: str,
        arguments: dict[str, object],
    ) -> tuple[list[SearchResult], ResearchToolCall]:
        result = await self.registry.invoke(name, arguments)
        if isinstance(result, list):
            evidence = result
            summary = f"Retrieved {len(evidence)} passage(s)."
        elif isinstance(result, ResearchComparison):
            evidence = [*result.evidence_a, *result.evidence_b]
            summary = f"Retrieved {len(evidence)} passage(s) across two documents."
        else:
            raise RuntimeError("The research executor received an unsupported tool result.")
        return evidence, ResearchToolCall(
            name=name,
            arguments=arguments,
            status=ResearchStepStatus.COMPLETED,
            result_summary=summary,
        )

    async def execute_tools(
        self, state: ResearchGraphState, *, remaining_tool_calls: int
    ) -> tuple[Sequence[SearchResult], Sequence[ResearchToolCall]]:
        if remaining_tool_calls < 1:
            raise ResearchToolError("TOOL_CALL_LIMIT_REACHED")
        query = state["subquestions"][0] if state["subquestions"] else state["query"]
        allowed_doc_ids = state["allowed_doc_ids"]
        if state["iterations"] == 0:
            search_results, search_call = await self._invoke(
                "search_documents",
                {
                    "query": query,
                    "doc_ids": allowed_doc_ids,
                    "top_k": min(10, state["top_k"]),
                },
            )
            evidence, calls = list(search_results), [search_call]
            if remaining_tool_calls > 1 and len(allowed_doc_ids) >= 2:
                comparison, compare_call = await self._invoke(
                    "compare_sections",
                    {
                        "doc_a_id": allowed_doc_ids[0],
                        "doc_b_id": allowed_doc_ids[1],
                        "topic": query,
                    },
                )
                evidence.extend(comparison)
                calls.append(compare_call)
            return evidence, calls

        covered_doc_ids = {
            item.document_id
            for item in state["retrieved_evidence"]
            if item.cosine_similarity > self.settings.retrieval_similarity_threshold
        }
        missing_doc_ids = [
            identity for identity in allowed_doc_ids if identity not in covered_doc_ids
        ]
        if missing_doc_ids:
            target_id = missing_doc_ids[0]
        else:
            best_scores = {
                identity: max(
                    (
                        item.cosine_similarity
                        for item in state["retrieved_evidence"]
                        if item.document_id == identity
                    ),
                    default=-1.0,
                )
                for identity in allowed_doc_ids
            }
            target_id = min(best_scores, key=best_scores.__getitem__)
        evidence, call = await self._invoke(
            "search_documents",
            {"query": query, "doc_ids": [target_id], "top_k": min(3, state["top_k"])},
        )
        return evidence, [call]

    async def assess_sufficiency(self, state: ResearchGraphState) -> bool:
        covered = {
            item.document_id
            for item in state["retrieved_evidence"]
            if item.cosine_similarity > self.settings.retrieval_similarity_threshold
        }
        return len(state["retrieved_evidence"]) >= 2 and set(state["allowed_doc_ids"]).issubset(
            covered
        )

    async def retrieve_more(self, state: ResearchGraphState) -> Sequence[SearchResult]:
        return []

    @staticmethod
    def _retrieved_chunks(evidence: Sequence[SearchResult]) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                page_number=item.page_number,
                chunk_index=item.chunk_index,
                text=item.text,
                cosine_similarity=item.cosine_similarity,
                fusion_score=item.fusion_score,
                context_group=item.context_group,
                is_adjacent_context=item.is_adjacent_context,
                rerank_score=item.rerank_score,
            )
            for item in evidence
        ]

    @staticmethod
    def _partial_report(title: str, disclaimer: str) -> ResearchReport:
        return ResearchReport(
            title=title[:200] or "Research report",
            summary=INSUFFICIENT_ANSWER,
            partial_coverage=True,
            disclaimer=disclaimer,
        )

    async def synthesize(self, state: ResearchGraphState) -> ResearchReport:
        title = state["query"][:200] or "Research report"
        if not state["retrieved_evidence"]:
            return self._partial_report(title, "No relevant evidence was retrieved.")

        generation = await self.llm_provider.generate(
            state["query"], self._retrieved_chunks(state["retrieved_evidence"])
        )
        draft = generation.response
        citations = verify_citations(draft, generation.passages)
        if (
            draft.insufficient_evidence
            or not citations
            or not answer_is_covered(draft.answer, citations)
        ):
            return self._partial_report(
                title, "The retrieved sources did not support a fully cited report."
            )
        return ResearchReport(
            title=title,
            summary=draft.answer,
            sections=[ResearchSection(heading="Findings", content=draft.answer)],
            citations=citations,
            partial_coverage=not bool(state["sufficiency_verdict"]),
            disclaimer=(
                "The workflow reached its execution budget; this report may have partial coverage."
                if not state["sufficiency_verdict"]
                else None
            ),
        )

    async def verify_citations(
        self, report: ResearchReport, state: ResearchGraphState
    ) -> ResearchReport:
        source_by_id = {item.chunk_id: item for item in state["retrieved_evidence"]}
        narrative = " ".join([report.summary, *(section.content for section in report.sections)])
        verified = []
        for citation in report.citations:
            source = source_by_id.get(citation.chunk_id)
            if (
                source is None
                or source.document_id != citation.document_id
                or source.page_number != citation.page_number
                or not 0 <= citation.quote_start < citation.quote_end <= len(source.text)
                or source.text[citation.quote_start : citation.quote_end] != citation.quote
                or citation.claim not in narrative
            ):
                continue
            verified.append(citation)
        if not verified or not answer_is_covered(report.summary, verified):
            return self._partial_report(
                report.title, "The final citation check could not verify every report claim."
            )
        return report.model_copy(update={"citations": verified})


async def execute_research_job(
    database: Database,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    settings: Settings,
    *,
    session_id: UUID,
    allowed_doc_ids: list[UUID],
    query: str,
    top_k: int,
    budget: ResearchToolBudget,
    on_step: ResearchStepCallback,
) -> ResearchGraphState:
    """Run a bounded graph; concrete persistence is managed by the API worker."""
    tools = ResearchTools(
        database,
        embedding_provider,
        settings,
        session_id=session_id,
        allowed_doc_ids=allowed_doc_ids,
    )
    operations = AgentResearchOperations(
        ResearchToolRegistry(tools, budget), llm_provider, settings
    )
    graph = build_research_graph(
        operations,
        llm_timeout_seconds=settings.llm_timeout_seconds,
        max_iterations=settings.max_agent_iterations,
        max_tool_calls=settings.max_tool_calls,
        on_step=on_step,
    )
    request = ResearchRequest(query=query, document_ids=allowed_doc_ids, top_k=top_k)
    state = initial_research_state(request, session_id=session_id, allowed_doc_ids=allowed_doc_ids)
    return cast(ResearchGraphState, await graph.ainvoke(state))
