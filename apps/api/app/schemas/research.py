"""Validated contracts for bounded, session-scoped research workflows."""

from enum import StrEnum
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.answers import GroundedCitation
from app.schemas.retrieval import SearchResult


class ResearchStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ResearchToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    arguments: dict[str, object] = Field(default_factory=dict)
    status: ResearchStepStatus
    result_summary: str | None = Field(default=None, max_length=500)


class ResearchStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    status: ResearchStepStatus
    message: str = Field(max_length=500)
    iteration: int = Field(ge=0, le=4)
    tool_calls_count: int = Field(ge=0, le=6)


class ResearchSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)


class ResearchReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=5000)
    sections: list[ResearchSection] = Field(default_factory=list, max_length=20)
    citations: list[GroundedCitation] = Field(default_factory=list, max_length=100)
    partial_coverage: bool = False
    disclaimer: str | None = Field(default=None, max_length=500)


class SearchDocumentsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    doc_ids: list[UUID] = Field(min_length=1, max_length=10)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query must not be blank.")
        return value

    @field_validator("doc_ids")
    @classmethod
    def unique_document_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Document IDs must be unique.")
        return value


class DocumentOutlineArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: UUID


class CompareSectionsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_a_id: UUID
    doc_b_id: UUID
    topic: str = Field(min_length=1, max_length=1000)

    @field_validator("topic")
    @classmethod
    def nonblank_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comparison topic must not be blank.")
        return value

    @model_validator(mode="after")
    def distinct_documents(self) -> "CompareSectionsArguments":
        if self.doc_a_id == self.doc_b_id:
            raise ValueError("Comparison requires two different documents.")
        return self


class OutlineSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str = Field(min_length=1, max_length=300)
    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)


class DocumentOutline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    filename: str = Field(min_length=1, max_length=255)
    page_count: int | None = Field(default=None, ge=1, le=100)
    sections: list[OutlineSection] = Field(min_length=1, max_length=100)


class ResearchComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=1000)
    doc_a_id: UUID
    doc_b_id: UUID
    evidence_a: list[SearchResult] = Field(default_factory=list, max_length=3)
    evidence_b: list[SearchResult] = Field(default_factory=list, max_length=3)


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] = Field(min_length=2, max_length=10)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query must not be blank.")
        return value

    @field_validator("document_ids")
    @classmethod
    def unique_document_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Document IDs must be unique.")
        return value


class ResearchJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status: ResearchStatus
    query: str
    steps: list[ResearchStep] = Field(default_factory=list)
    tool_calls: list[ResearchToolCall] = Field(default_factory=list)
    iterations: int = Field(default=0, ge=0, le=4)
    tool_calls_count: int = Field(default=0, ge=0, le=6)
    sufficiency_verdict: bool | None = None
    report: ResearchReport | None = None
    error_code: str | None = Field(default=None, max_length=64)
    evidence: list[SearchResult] = Field(default_factory=list)


class ResearchGraphState(TypedDict):
    query: str
    session_id: UUID
    allowed_doc_ids: list[UUID]
    top_k: int
    subquestions: list[str]
    retrieved_evidence: list[SearchResult]
    tool_calls: list[ResearchToolCall]
    tool_calls_count: int
    iterations: int
    sufficiency_verdict: bool | None
    final_report: ResearchReport | None
    status: ResearchStatus
    steps: list[ResearchStep]
    error_code: str | None
