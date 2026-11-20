"""Markdown-aware token windows with exact offsets into original page Markdown."""

import re
from collections.abc import Callable
from hashlib import sha256
from uuid import UUID, uuid5

from app.schemas.chunks import ChunkSchema
from app.services.chunking.markdown import markdown_blocks
from app.services.chunking.tokenizer import token_count
from app.services.ingestion.normalization import NormalizedDocument, NormalizedPage


def _fit_end(text: str, start: int, budget: int, count: Callable[[str], int] = token_count) -> int:
    low, high = start, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if count(text[start:middle]) <= budget:
            low = middle
        else:
            high = middle - 1
    while low > start and count(text[start:low]) > budget:
        low -= 1
    return max(start + 1, low)


def _overlap_start(
    text: str, start: int, end: int, budget: int, count: Callable[[str], int] = token_count
) -> int:
    low, high = start, end
    while low < high:
        middle = (low + high) // 2
        if count(text[middle:end]) <= budget:
            high = middle
        else:
            low = middle + 1
    return low


class MarkdownChunker:
    def __init__(
        self,
        *,
        min_tokens: int = 600,
        max_tokens: int = 800,
        overlap_tokens: int = 100,
        count_tokens: Callable[[str], int] = token_count,
        tokenizer_name: str = "cl100k_base",
        split_oversized_atomic: bool = False,
    ) -> None:
        if not 0 <= overlap_tokens < min_tokens <= max_tokens:
            raise ValueError("Chunk budgets require 0 <= overlap < minimum <= maximum")
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.count_tokens = count_tokens
        self.tokenizer_name = tokenizer_name
        self.split_oversized_atomic = split_oversized_atomic

    def _page_spans(self, page: NormalizedPage) -> list[tuple[int, int, bool]]:
        text = page.normalized_text
        blocks = markdown_blocks(text)
        all_atomic = [block for block in blocks if block.kind in {"table", "code"}]
        oversized_atomic = (
            [
                block
                for block in all_atomic
                if self.count_tokens(text[block.start : block.end]) > self.max_tokens
            ]
            if self.split_oversized_atomic
            else []
        )
        atomic = [block for block in all_atomic if block not in oversized_atomic]
        result: list[tuple[int, int, bool]] = []
        start = 0
        while start < len(text):
            while start < len(text) and text[start].isspace():
                start += 1
            if start == len(text):
                break
            hard_end = _fit_end(text, start, self.max_tokens, self.count_tokens)
            crossing = next((block for block in atomic if block.start < hard_end < block.end), None)
            oversized = False
            if crossing:
                if crossing.start > start and text[start : crossing.start].strip():
                    hard_end = crossing.start
                else:
                    hard_end = crossing.end
                    oversized = self.count_tokens(text[start:hard_end]) > self.max_tokens
            else:
                large_crossing = next(
                    (block for block in oversized_atomic if block.start < hard_end < block.end),
                    None,
                )
                if large_crossing and large_crossing.start > start:
                    hard_end = large_crossing.start
            end = hard_end
            large_block = next(
                (block for block in oversized_atomic if block.start <= start < block.end), None
            )
            if large_block:
                line_ends = [
                    large_block.start + match.end()
                    for match in re.finditer(r"\n", text[large_block.start : large_block.end])
                    if start < large_block.start + match.end() <= hard_end
                ]
                eligible = [
                    offset
                    for offset in line_ends
                    if self.count_tokens(text[start:offset]) >= self.min_tokens
                ]
                if eligible:
                    end = max(eligible)
                elif line_ends:
                    end = max(line_ends)
            elif hard_end < len(text) and not oversized:
                # Prefer a section boundary, then paragraphs, sentences, words,
                # finally Unicode character boundaries for an indivisible long word.
                headings = [
                    block.start
                    for block in blocks
                    if block.kind == "heading" and start < block.start <= hard_end
                ]
                paragraph_ends = [
                    block.end
                    for block in blocks
                    if start < block.end <= hard_end and block.kind != "blank"
                ]
                for boundaries in (headings, paragraph_ends):
                    eligible = [
                        offset
                        for offset in boundaries
                        if self.count_tokens(text[start:offset]) >= self.min_tokens
                    ]
                    if eligible:
                        end = max(eligible)
                        break
                else:
                    for pattern in (r"[.!?]\s+", r"\s+"):
                        candidates = [
                            start + match.end()
                            for match in re.finditer(pattern, text[start:hard_end])
                        ]
                        eligible = [
                            offset
                            for offset in candidates
                            if self.count_tokens(text[start:offset]) >= self.min_tokens
                        ]
                        if eligible:
                            end = max(eligible)
                            break
            # Natural boundaries must not split a protected Markdown block either.
            containing = next((block for block in atomic if block.start < end < block.end), None)
            if containing:
                end = containing.start if containing.start > start else containing.end
            while end > start and text[end - 1].isspace():
                end -= 1
            if end <= start:
                raise ValueError("Chunker made no progress")
            if result and end <= result[-1][1]:
                # An atomic block may not fit alongside overlap. Drop that overlap
                # rather than repeatedly emitting the same prefix before the block.
                start = max(start + 1, result[-1][1])
                continue
            oversized = self.count_tokens(text[start:end]) > self.max_tokens
            result.append((start, end, oversized))
            if not text[end:].strip():
                break
            next_start = _overlap_start(text, start, end, self.overlap_tokens, self.count_tokens)
            overlapped_atomic = next(
                (block for block in atomic if block.start <= next_start < block.end), None
            )
            if overlapped_atomic:
                next_start = overlapped_atomic.end
            else:
                overlapped_large = next(
                    (block for block in oversized_atomic if block.start < next_start < block.end),
                    None,
                )
                if overlapped_large:
                    overlap_line_ends = (
                        overlapped_large.start + match.end()
                        for match in re.finditer(
                            r"\n", text[overlapped_large.start : overlapped_large.end]
                        )
                    )
                    next_start = next(
                        (offset for offset in overlap_line_ends if next_start <= offset <= end),
                        next_start,
                    )
            start = max(start + 1, next_start)
        return result

    def split(self, document: NormalizedDocument, *, document_id: UUID) -> tuple[ChunkSchema, ...]:
        chunks: list[ChunkSchema] = []
        for page in document.pages:
            for start, end, oversized in self._page_spans(page):
                raw_start, raw_end = page.raw_span(start, end)
                normalized = page.normalized_text[start:end]
                digest = sha256(normalized.encode()).hexdigest()
                identity = f"{page.page_number}:{raw_start}:{raw_end}:{digest}"
                chunks.append(
                    ChunkSchema(
                        id=str(uuid5(document_id, identity)),
                        document_id=str(document_id),
                        chunk_index=len(chunks),
                        raw_text=page.raw_text[raw_start:raw_end],
                        normalized_text=normalized,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        char_start=raw_start,
                        char_end=raw_end,
                        metadata={
                            "token_count": self.count_tokens(normalized),
                            "tokenizer": self.tokenizer_name,
                            "oversized_atomic": oversized,
                            "normalized_char_start": start,
                            "normalized_char_end": end,
                        },
                    )
                )
        return tuple(chunks)
