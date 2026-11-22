"""Generate grounded answers, verify their citations, and provide safe fallbacks."""

import logging
from collections.abc import Sequence

from app.providers.llm import LLMProvider, LLMProviderError, LLMRateLimitError, LLMTimeoutError
from app.schemas.answers import AnswerResponse, UsedEvidence
from app.schemas.retrieval import SearchResult
from app.services.generation.citations import answer_is_covered, verify_citations
from app.services.generation.evidence import EvidencePassage
from app.services.retrieval.dense import RetrievedChunk

UNAVAILABLE_ANSWER = (
    "Answer generation is temporarily unavailable. Review the retrieved evidence below."
)
INSUFFICIENT_ANSWER = "I could not find enough relevant evidence to answer this question."
logger = logging.getLogger("research.generation")


def _evidence_response(evidence: Sequence[RetrievedChunk]) -> list[SearchResult]:
    return [SearchResult.model_validate(item) for item in evidence]


def _used_evidence(
    passages: Sequence[EvidencePassage], evidence: Sequence[RetrievedChunk]
) -> list[UsedEvidence]:
    used: list[UsedEvidence] = []
    for context_index, passage in enumerate(passages):
        if (
            not 0 <= passage.retrieval_index < len(evidence)
            or passage.source != evidence[passage.retrieval_index]
            or not 0 <= passage.start < passage.end <= len(passage.source.text)
        ):
            raise LLMProviderError("The generation context does not match retrieved evidence.")
        source = passage.source
        used.append(
            UsedEvidence(
                context_index=context_index,
                retrieval_index=passage.retrieval_index,
                start=passage.start,
                end=passage.end,
                **SearchResult.model_validate(source)
                .model_copy(update={"text": passage.text})
                .model_dump(),
            )
        )
    return used


async def generate_answer(
    provider: LLMProvider,
    question: str,
    evidence: Sequence[RetrievedChunk],
    *,
    similarity_threshold: float,
) -> AnswerResponse:
    insufficient = (
        not evidence or max(item.cosine_similarity for item in evidence) <= similarity_threshold
    )
    snippets = _evidence_response(evidence)
    if insufficient:
        return AnswerResponse(
            answer=INSUFFICIENT_ANSWER,
            citations=[],
            insufficient_evidence=True,
            degraded_mode=False,
            evidence=snippets,
        )

    try:
        generation = await provider.generate(question, evidence)
    except (LLMTimeoutError, LLMRateLimitError) as exc:
        logger.warning("answer.llm_degraded", extra={"error_code": exc.error_code})
        return AnswerResponse(
            answer=UNAVAILABLE_ANSWER,
            citations=[],
            insufficient_evidence=False,
            degraded_mode=True,
            evidence=snippets,
        )

    draft = generation.response
    used_evidence = _used_evidence(generation.passages, evidence)
    citations = verify_citations(draft, generation.passages)
    if (
        draft.insufficient_evidence
        or not citations
        or not answer_is_covered(draft.answer, citations)
    ):
        return AnswerResponse(
            answer=INSUFFICIENT_ANSWER,
            citations=[],
            insufficient_evidence=True,
            degraded_mode=False,
            evidence=snippets,
            used_evidence=used_evidence,
        )
    return AnswerResponse(
        answer=draft.answer,
        citations=citations,
        insufficient_evidence=draft.insufficient_evidence,
        degraded_mode=False,
        evidence=snippets,
        used_evidence=used_evidence,
    )
