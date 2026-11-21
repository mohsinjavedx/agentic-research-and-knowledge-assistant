import asyncio
from collections.abc import Sequence
from uuid import UUID

import pytest

from app.providers.llm import GenerationResult
from app.schemas.answers import GeneratedCitation, GroundedResponse
from app.services.generation.answer import generate_answer
from app.services.generation.evidence import EvidencePassage
from app.services.retrieval.dense import RetrievedChunk

FACT = "The benchmarks are Alpha, Beta, and Gamma."


class Provider:
    def __init__(self, response: GroundedResponse, *, focused: bool = False) -> None:
        self.response = response
        self.focused = focused

    async def generate(self, question: str, evidence: Sequence[RetrievedChunk]) -> GenerationResult:
        source = evidence[-1]
        start = source.text.index(FACT) if self.focused else 0
        end = start + len(FACT) if self.focused else len(source.text)
        return GenerationResult(
            self.response, [EvidencePassage(source, len(evidence) - 1, start, end)]
        )

    def close(self) -> None:
        pass


def run_answer(answer: str, claim: str, quote: str, *, text: str = FACT, focused: bool = False):
    source = RetrievedChunk(UUID(int=1), UUID(int=100), 7, 3, text, 0.8)
    provider = Provider(
        GroundedResponse(
            answer=answer,
            insufficient_evidence=False,
            citations=[GeneratedCitation(claim=claim, quote=quote, evidence_index=0)],
        ),
        focused=focused,
    )
    return asyncio.run(
        generate_answer(provider, "Which benchmarks?", [source], similarity_threshold=0.5)
    )


def test_public_citation_has_an_exact_quote_and_offsets_in_the_original_chunk() -> None:
    text = "Café background.\n\n" + FACT + "\n\nUnrelated closing."
    result = run_answer(FACT, FACT, FACT, text=text, focused=True)
    assert result.answer == FACT
    citation = result.citations[0]
    assert citation.quote == FACT
    assert text[citation.quote_start : citation.quote_end] == citation.quote
    assert result.used_evidence[0].text == FACT
    assert result.used_evidence[0].start == text.index(FACT)
    assert result.used_evidence[0].context_index == 0
    assert result.evidence[0].text == text


def test_generic_citation_claim_is_rejected_even_with_a_real_source_quote() -> None:
    result = run_answer(FACT, "Five representative datasets cover different domains.", FACT)
    assert result.insufficient_evidence is True
    assert result.citations == []


def test_invented_quote_is_rejected_even_when_the_source_id_is_valid() -> None:
    result = run_answer(FACT, FACT, "The benchmarks are Delta and Epsilon.")
    assert result.insufficient_evidence is True


def test_source_quote_must_be_in_the_passage_actually_supplied_to_the_model() -> None:
    result = run_answer(
        FACT, FACT, "Private background.", text="Private background.\n\n" + FACT, focused=True
    )
    assert result.insufficient_evidence is True


def test_a_cited_sentence_does_not_permit_an_additional_uncited_claim() -> None:
    result = run_answer(FACT + " It achieved 99% accuracy.", FACT, FACT)
    assert result.insufficient_evidence is True
    assert result.citations == []


def test_quote_whitespace_is_matched_without_changing_the_returned_source_text() -> None:
    source = "The benchmarks are Alpha,\n Beta, and Gamma."
    result = run_answer(FACT, FACT, FACT, text=source)
    assert result.insufficient_evidence is False
    assert result.citations[0].quote == source


def test_quote_entities_map_to_original_unicode_codepoint_offsets() -> None:
    result = run_answer("A & B", "A & B", "A &amp; B", text="🧪 A & B")
    assert result.insufficient_evidence is False
    assert result.citations[0].quote == "A & B"
    assert result.citations[0].quote_start == 2
    assert result.citations[0].quote_end == 7


def test_context_indices_map_to_used_sources_instead_of_original_retrieval_order() -> None:
    sources = [
        RetrievedChunk(UUID(int=1), UUID(int=100), 1, 0, "Unused background.", 0.8),
        RetrievedChunk(UUID(int=2), UUID(int=100), 7, 1, FACT, 0.7),
    ]
    provider = Provider(
        GroundedResponse(
            answer=FACT,
            insufficient_evidence=False,
            citations=[GeneratedCitation(claim=FACT, quote=FACT, evidence_index=0)],
        )
    )
    result = asyncio.run(
        generate_answer(provider, "Which benchmarks?", sources, similarity_threshold=0.5)
    )
    assert result.citations[0].chunk_id == UUID(int=2)
    assert result.used_evidence[0].context_index == 0
    assert result.used_evidence[0].retrieval_index == 1


@pytest.mark.parametrize("answer,claim", [("−5%", "5%"), ("<5", "5"), ("$25", "25"), ("25%", "25")])
def test_meaning_bearing_symbols_cannot_be_added_outside_the_cited_claim(
    answer: str, claim: str
) -> None:
    result = run_answer(answer, claim, claim, text=claim)
    assert result.insufficient_evidence is True
    assert result.citations == []
