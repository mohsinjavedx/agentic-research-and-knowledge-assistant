"""Strict, read-only research tools constrained to the current session scope."""

import asyncio
import re
from collections.abc import Sequence
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Chunk, Document
from app.db.session import Database
from app.providers.embeddings import EmbeddingProvider
from app.schemas.research import (
    CompareSectionsArguments,
    DocumentOutline,
    DocumentOutlineArguments,
    OutlineSection,
    ResearchComparison,
    SearchDocumentsArguments,
)
from app.schemas.retrieval import SearchResult
from app.services.chunking.markdown import HEADING, markdown_blocks
from app.services.retrieval.dense import RetrievedChunk
from app.services.retrieval.scope import visible_document_ids
from app.services.retrieval.search import search_evidence

type ResearchToolResult = list[SearchResult] | DocumentOutline | ResearchComparison


class ResearchToolError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


class ResearchToolBudget:
    def __init__(self, max_tool_calls: int = 6) -> None:
        if not 1 <= max_tool_calls <= 6:
            raise ValueError("Research tool calls must be capped at six.")
        self.max_tool_calls = max_tool_calls
        self.tool_calls_count = 0
        self._lock = asyncio.Lock()

    async def reserve(self) -> None:
        async with self._lock:
            if self.tool_calls_count >= self.max_tool_calls:
                raise ResearchToolError("TOOL_CALL_LIMIT_REACHED")
            self.tool_calls_count += 1


def _search_results(chunks: Sequence[RetrievedChunk]) -> list[SearchResult]:
    return [SearchResult.model_validate(chunk) for chunk in chunks]


def _outline_sections(
    chunks: Sequence[tuple[int, int, str]],
) -> list[OutlineSection]:
    sections: list[OutlineSection] = []
    seen: set[tuple[str, int]] = set()
    for chunk_index, page_number, text in chunks:
        for block in markdown_blocks(text):
            if block.kind != "heading":
                continue
            heading = text[block.start : block.end].strip()
            match = HEADING.match(heading)
            if match is None:
                continue
            heading = re.sub(r"^\s{0,3}#{1,6}\s+", "", heading).strip()
            identity = heading, page_number
            if heading and identity not in seen:
                sections.append(
                    OutlineSection(
                        heading=heading[:300],
                        page_number=page_number,
                        chunk_index=chunk_index,
                    )
                )
                seen.add(identity)
    if sections:
        return sections[:100]

    for chunk_index, page_number, _ in chunks:
        identity = f"Page {page_number}", page_number
        if identity not in seen:
            sections.append(
                OutlineSection(
                    heading=identity[0],
                    page_number=page_number,
                    chunk_index=chunk_index,
                )
            )
            seen.add(identity)
    return sections[:100]


class ResearchTools:
    def __init__(
        self,
        database: Database,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
        *,
        session_id: UUID,
        allowed_doc_ids: list[UUID],
    ) -> None:
        if len(allowed_doc_ids) < 2 or len(allowed_doc_ids) != len(set(allowed_doc_ids)):
            raise ValueError("Research tools require a unique multi-document visible scope.")
        self.database = database
        self.embedding_provider = embedding_provider
        self.settings = settings
        self.session_id = session_id
        self.allowed_doc_ids = tuple(allowed_doc_ids)

    async def _validate_scope(self, selected_doc_ids: Sequence[UUID]) -> list[UUID]:
        if not selected_doc_ids or not set(selected_doc_ids).issubset(self.allowed_doc_ids):
            raise ResearchToolError("DOCUMENT_OUTSIDE_RESEARCH_SCOPE")
        visible_ids = await visible_document_ids(
            self.database, self.session_id, list(selected_doc_ids)
        )
        if set(visible_ids) != set(selected_doc_ids):
            raise ResearchToolError("DOCUMENT_NOT_FOUND")
        return list(selected_doc_ids)

    async def search_documents(self, arguments: SearchDocumentsArguments) -> list[SearchResult]:
        doc_ids = await self._validate_scope(arguments.doc_ids)
        chunks = await search_evidence(
            self.database,
            self.embedding_provider,
            arguments.query,
            doc_ids,
            top_k=arguments.top_k,
            mode=self.settings.retrieval_mode,
        )
        return _search_results(chunks)

    async def get_document_outline(self, arguments: DocumentOutlineArguments) -> DocumentOutline:
        doc_ids = await self._validate_scope([arguments.doc_id])
        statement = (
            select(
                Document.filename,
                Document.page_count,
                Chunk.chunk_index,
                Chunk.page_start,
                Chunk.normalized_text,
            )
            .join(Chunk, Chunk.document_id == Document.id)
            .where(
                Document.id.in_(doc_ids),
                Document.id.in_(self.allowed_doc_ids),
                Document.status == "ready",
            )
            .order_by(Chunk.chunk_index)
        )
        async with self.database.sessions() as session:
            rows = (await session.execute(statement)).all()
        if not rows:
            raise ResearchToolError("DOCUMENT_OUTLINE_UNAVAILABLE")
        filename, page_count = rows[0][0], rows[0][1]
        chunks = [(row[2], row[3], row[4]) for row in rows]
        return DocumentOutline(
            document_id=arguments.doc_id,
            filename=filename,
            page_count=page_count,
            sections=_outline_sections(chunks),
        )

    async def compare_sections(self, arguments: CompareSectionsArguments) -> ResearchComparison:
        doc_ids = await self._validate_scope([arguments.doc_a_id, arguments.doc_b_id])
        evidence_a, evidence_b = await asyncio.gather(
            search_evidence(
                self.database,
                self.embedding_provider,
                arguments.topic,
                [doc_ids[0]],
                top_k=3,
                mode=self.settings.retrieval_mode,
            ),
            search_evidence(
                self.database,
                self.embedding_provider,
                arguments.topic,
                [doc_ids[1]],
                top_k=3,
                mode=self.settings.retrieval_mode,
            ),
        )
        return ResearchComparison(
            topic=arguments.topic,
            doc_a_id=doc_ids[0],
            doc_b_id=doc_ids[1],
            evidence_a=_search_results(evidence_a),
            evidence_b=_search_results(evidence_b),
        )


class ResearchToolRegistry:
    """Dispatch only the three documented tools after strict argument validation."""

    def __init__(self, tools: ResearchTools, budget: ResearchToolBudget | None = None) -> None:
        self.tools = tools
        self.budget = budget or ResearchToolBudget()

    async def invoke(self, name: str, arguments: dict[str, object]) -> ResearchToolResult:
        if name == "search_documents":
            try:
                search_arguments = SearchDocumentsArguments.model_validate(arguments)
            except ValidationError:
                raise ResearchToolError("INVALID_TOOL_ARGUMENTS") from None
            await self.budget.reserve()
            return await self.tools.search_documents(search_arguments)
        if name == "get_document_outline":
            try:
                outline_arguments = DocumentOutlineArguments.model_validate(arguments)
            except ValidationError:
                raise ResearchToolError("INVALID_TOOL_ARGUMENTS") from None
            await self.budget.reserve()
            return await self.tools.get_document_outline(outline_arguments)
        if name == "compare_sections":
            try:
                comparison_arguments = CompareSectionsArguments.model_validate(arguments)
            except ValidationError:
                raise ResearchToolError("INVALID_TOOL_ARGUMENTS") from None
            await self.budget.reserve()
            return await self.tools.compare_sections(comparison_arguments)
        raise ResearchToolError("TOOL_NOT_ALLOWED")
