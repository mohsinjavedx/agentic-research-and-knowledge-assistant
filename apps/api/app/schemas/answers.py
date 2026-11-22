"""Strict structured outputs and HTTP contracts for evidence-grounded answers."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.retrieval import ContextGroup, SearchRequest, SearchResult


class GroundedCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=2000)
    chunk_id: UUID
    document_id: UUID
    page_number: int = Field(ge=1)
    quote: str = Field(min_length=1)
    quote_start: int = Field(ge=0)
    quote_end: int = Field(gt=0)

    @field_validator("claim")
    @classmethod
    def nonblank_claim(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Citation claims must not be blank.")
        return value


class GeneratedCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=2000)
    evidence_index: int = Field(ge=0)
    quote: str = Field(min_length=1, max_length=4000)

    @field_validator("claim")
    @classmethod
    def nonblank_claim(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Citation claims must not be blank.")
        return value


class GroundedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(max_length=10000)
    citations: list[GeneratedCitation] = Field(max_length=20)
    insufficient_evidence: bool

    @field_validator("answer")
    @classmethod
    def trim_answer(cls, value: str) -> str:
        return value.strip()


class AnswerRequest(SearchRequest):
    top_k: int = Field(default=5, ge=1, le=10)


class UsedEvidence(SearchResult):
    context_index: int = Field(ge=0)
    retrieval_index: int = Field(ge=0)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class AnswerResponse(BaseModel):
    answer: str
    citations: list[GroundedCitation]
    insufficient_evidence: bool
    degraded_mode: bool
    evidence: list[SearchResult] = Field(default_factory=list)
    used_evidence: list[UsedEvidence] = Field(default_factory=list)
    ranked_chunk_ids: list[UUID] = Field(default_factory=list)
    context_groups: list[ContextGroup] = Field(default_factory=list)
    reranking_applied: bool = False
    reranker_error: str | None = None
