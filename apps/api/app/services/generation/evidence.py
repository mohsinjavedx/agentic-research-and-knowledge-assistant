"""Select complete source blocks without rewriting their text or losing offsets."""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.services.chunking.markdown import MarkdownBlock, markdown_blocks
from app.services.retrieval.dense import RetrievedChunk

STOP_WORDS = frozenset(
    "a an and are as at be been by did do does for from had has have how in into is it of on or "
    "that the their these this those to was were what when where which who why with would "
    "used using according paper study proposed reported system".split()
)


def _terms(text: str) -> set[str]:
    return {
        word.rstrip("s")
        for word in re.findall(r"[^\W_]+", text.casefold())
        if word not in STOP_WORDS and (len(word) > 1 or word.isdigit())
    }


@dataclass(frozen=True)
class EvidencePassage:
    source: RetrievedChunk
    retrieval_index: int
    start: int
    end: int

    @property
    def text(self) -> str:
        return self.source.text[self.start : self.end]

    def prompt_chunk(self) -> RetrievedChunk:
        return replace(self.source, text=self.text)


def _is_heading(block: MarkdownBlock, text: str) -> bool:
    return block.kind == "heading" or bool(re.fullmatch(r"\*\*[^*\n]+\*\*", text.strip()))


def _starts_list(text: str) -> bool:
    return bool(re.match(r"\s*(?:[-*+] |\d+[.)] )", text))


def _atomic_blocks(text: str) -> list[MarkdownBlock]:
    blocks = [block for block in markdown_blocks(text) if block.kind != "blank"]
    grouped: list[MarkdownBlock] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if not _starts_list(text[block.start : block.end]):
            grouped.append(block)
            index += 1
            continue
        start, end = block.start, block.end
        if (
            grouped
            and grouped[-1].kind == "paragraph"
            and text[grouped[-1].start : grouped[-1].end].rstrip().endswith(":")
        ):
            start = grouped.pop().start
        index += 1
        while index < len(blocks):
            following = blocks[index]
            content = text[following.start : following.end]
            continuation = following.kind == "paragraph" and bool(re.match(r"[ \t]{2,}\S", content))
            if not (_starts_list(content) or continuation):
                break
            end = following.end
            index += 1
        grouped.append(MarkdownBlock(start, end, "paragraph"))
    return grouped


def focus_evidence(question: str, evidence: Sequence[RetrievedChunk]) -> list[EvidencePassage]:
    query_terms = _terms(question)
    parsed = [_atomic_blocks(item.text) for item in evidence]
    all_terms = [
        _terms(item.text[block.start : block.end])
        for item, blocks in zip(evidence, parsed, strict=True)
        for block in blocks
    ]
    weights = {
        term: math.log(1 + len(all_terms) / (1 + sum(term in terms for terms in all_terms)))
        for term in query_terms
    }
    passages: list[EvidencePassage] = []
    for retrieval_index, (item, blocks) in enumerate(zip(evidence, parsed, strict=True)):
        if item.context_group is not None:
            passages.append(EvidencePassage(item, retrieval_index, 0, len(item.text)))
            continue
        candidates = [
            (index, block)
            for index, block in enumerate(blocks)
            if not _is_heading(block, item.text[block.start : block.end])
        ]
        if not candidates:
            if item.text.strip():
                passages.append(EvidencePassage(item, retrieval_index, 0, len(item.text)))
            continue

        def score(candidate: tuple[int, MarkdownBlock], source: RetrievedChunk = item) -> float:
            _, block = candidate
            return sum(
                weights.get(term, 0.0) for term in _terms(source.text[block.start : block.end])
            )

        index, best = max(candidates, key=score)
        start, end = best.start, best.end
        if score((index, best)) == 0:
            start, end = 0, len(item.text)
        elif index:
            previous = blocks[index - 1]
            previous_text = item.text[previous.start : previous.end]
            if _is_heading(previous, previous_text) or best.kind == "table":
                start = previous.start
        while start < end and item.text[start].isspace():
            start += 1
        while end > start and item.text[end - 1].isspace():
            end -= 1
        passages.append(EvidencePassage(item, retrieval_index, start, end))
    ordered: list[EvidencePassage] = []
    seen_groups = set()
    for passage in passages:
        group = passage.source.context_group
        if group is None:
            ordered.append(passage)
        elif group not in seen_groups:
            seen_groups.add(group)
            ordered.extend(
                sorted(
                    (row for row in passages if row.source.context_group == group),
                    key=lambda row: row.source.chunk_index,
                )
            )
    return ordered
