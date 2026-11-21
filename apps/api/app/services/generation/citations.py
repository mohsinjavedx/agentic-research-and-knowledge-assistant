"""Check quote provenance and answer coverage; this is not an entailment model."""

import re
from collections.abc import Sequence
from html import unescape

from app.schemas.answers import GroundedCitation, GroundedResponse
from app.services.generation.evidence import EvidencePassage


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _quote_range(text: str, quote: str) -> tuple[int, int] | None:
    characters: list[str] = []
    positions: list[int] = []
    for word in re.finditer(r"\S+", text):
        if characters:
            characters.append(" ")
            positions.append(word.start())
        characters.extend(word.group())
        positions.extend(range(word.start(), word.end()))
    normalized_source = "".join(characters)
    for candidate in dict.fromkeys([_normalized(quote), _normalized(unescape(quote))]):
        if not candidate:
            continue
        index = normalized_source.find(candidate)
        if index >= 0:
            return positions[index], positions[index + len(candidate) - 1] + 1
    return None


def verify_citations(
    response: GroundedResponse, passages: Sequence[EvidencePassage]
) -> list[GroundedCitation]:
    verified: list[GroundedCitation] = []
    seen: set[tuple[int, str, int, int]] = set()
    answer = _normalized(response.answer)
    for citation in response.citations:
        if citation.evidence_index >= len(passages):
            continue
        claim = _normalized(citation.claim)
        if not claim or claim not in answer:
            continue
        passage = passages[citation.evidence_index]
        location = _quote_range(passage.text, citation.quote)
        if location is None:
            continue
        start, end = passage.start + location[0], passage.start + location[1]
        key = citation.evidence_index, claim, start, end
        if key in seen:
            continue
        seen.add(key)
        source = passage.source
        verified.append(
            GroundedCitation(
                claim=citation.claim,
                chunk_id=source.chunk_id,
                document_id=source.document_id,
                page_number=source.page_number,
                quote=source.text[start:end],
                quote_start=start,
                quote_end=end,
            )
        )
    return verified


def answer_is_covered(answer: str, citations: Sequence[GroundedCitation]) -> bool:
    normalized = _normalized(answer)
    covered = [False] * len(normalized)
    for citation in citations:
        claim = _normalized(citation.claim)
        for match in re.finditer(re.escape(claim), normalized):
            covered[match.start() : match.end()] = [True] * (match.end() - match.start())
    return bool(normalized) and all(
        covered[index] or character.isspace() for index, character in enumerate(normalized)
    )
