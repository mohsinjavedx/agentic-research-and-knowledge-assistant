from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=50)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query must not be blank.")
        return value

    @field_validator("document_ids")
    @classmethod
    def unique_document_ids(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Document IDs must be unique.")
        return value


class SearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    document_id: UUID
    page_number: int
    chunk_index: int
    text: str
    cosine_similarity: float
    fusion_score: float | None = None
    context_group: UUID | None = None
    is_adjacent_context: bool = False
    rerank_score: float | None = None

    @field_validator("cosine_similarity")
    @classmethod
    def rounded_similarity(cls, value: float) -> float:
        return round(value, 6)


class ContextGroup(BaseModel):
    anchor_id: UUID
    document_id: UUID
    chunk_ids: list[UUID]


class SearchResponse(BaseModel):
    results: list[SearchResult]
    similarity_threshold: float
    insufficient_evidence: bool
    retrieval_mode: Literal["dense", "hybrid"] = "dense"
    adjacent_context: list[SearchResult] = Field(default_factory=list)
    context_groups: list[ContextGroup] = Field(default_factory=list)
    reranking_applied: bool = False
    reranker_error: str | None = None
