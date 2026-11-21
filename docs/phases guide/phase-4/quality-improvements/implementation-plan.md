# Answer Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Improve answer relevance and citation traceability with a measured local retrieval/generation pipeline.

**Architecture:** PostgreSQL dense and full-text candidates share document scope and are fused by rank. Focused evidence retains original source ranges, and providers return the exact context alongside their structured draft. The answer service validates source quotes and answer coverage and exposes retrieved versus used evidence.

**Tech Stack:** Existing Python 3.12, FastAPI, PostgreSQL/pgvector, Pydantic, HTTPX, Ollama, pytest.

**Spec:** [design.md](design.md)

## Global Constraints

- Preserve all pending user work; work in place without staging, committing, merging, or pushing.
- Preserve original evaluation artifacts; new reports refuse overwrites.
- No new hosted service, embedding model, reindex, or database migration.
- Existing session, expiry, and sample visibility applies to every retrieval branch.
- Source quote checks establish provenance, not semantic entailment; human acceptance remains separate.

## Review Focus

- A keyword match must never expose another session's document.
- Fusion order differs from cosine order; abstention must use the best cosine evidence, not the first fused score.
- Focused text and quotes must map back exactly to the original normalized chunk, including Unicode and whitespace.
- A valid citation to one sentence must not allow additional uncited answer claims to escape.
- Failed, degraded, empty, or partially audited evaluation runs must not appear to pass quality gates.

### Task 1: Source audit and reproducible evaluation

**Files:** `data/eval/golden_set*.json`, `data/eval/label-audit-2026-11-21.json`, `scripts/run_retrieval_eval.py`, `apps/api/tests/unit/test_retrieval_runner.py`.

**Interfaces:** Evaluation accepts explicit dataset/output paths and retrieval mode; reports record dataset hash and per-query rankings.

- [x] Preserve the original dataset and reports; audit labels against original PDFs independently of ranking.
- [x] Add failing CLI tests for alternate dataset/output, preserved files, and per-query trace reporting.
- [x] Implement runner options and source-derived label corrections; verify focused tests.
- [x] Save a corrected dense baseline before enabling a new production retrieval default.

### Task 2: Scoped hybrid retrieval

**Files:** `apps/api/app/services/retrieval/hybrid.py`, `dense.py`, `app/api/v1/{search,answers}.py`, `app/core/config.py`, retrieval schemas/tests.

**Interfaces:** `retrieve_hybrid(database, query_vector, query, allowed_doc_ids, *, top_k=5)` returns ranked `RetrievedChunk` values with separate optional fusion scores. Shared dispatch preserves a dense option.

- [x] Write failing behavior tests for fusion/deduplication and a PostgreSQL case proving keyword recall and document isolation.
- [x] Implement scoped full-text candidates, rank fusion (60), and strategy selection with 20 candidates per branch.
- [x] Use maximum returned cosine for abstention and keep fusion scores separate from cosine.
- [x] Verify unit/integration tests and compare dense/hybrid on identical corrected labels; choose the default from evidence.

### Task 3: Focused evidence and checked citations

**Files:** `app/services/generation/{evidence,prompt,answer}.py`, `app/providers/llm.py`, `app/schemas/answers.py`, generation/provider/API tests.

**Interfaces:** `EvidencePassage` preserves original chunk, retrieval index, start/end; `GenerationResult` returns the structured response and actual passages. `AnswerResponse.used_evidence` exposes those passages. Generated citations include a source quote; public citations include its verified source range.

- [x] Write failing tests for relevant paragraph selection, whole lists/tables, source ranges, actual context reporting, invalid quotes, unrelated claims, and uncited answer text.
- [x] Implement focused passage selection and native context packing; preserve hosted compatibility and failure semantics.
- [x] Validate quotes against supplied passages and claims against answer text; reject incomplete coverage and explicit insufficiency.
- [x] Update deterministic API/provider fixtures and verify timeout/rate-limit fallback has no fabricated citations or used context claims.
- [x] Retest the user's exact query against the real API and include source-quote verification. **Verified after the Groq switch: correct five-name answer, page7 quote/ranges, HTTP200 in3.15s; preserved in the Groq benchmark smoke report.**

### Task 4: Evaluation, documentation, and final review

**Files:** `scripts/run_grounded_qa_eval.py`, evaluation reports, API contracts, this folder's six step guides and README.

- [x] Extend answer evaluation to retain used context, quote checks, status/errors, latency, and completed-answer counts.
- [x] Run the full backend suite, real database cases, Ruff, formatting, and mypy; resolve failures.
- [x] Run corrected retrieval comparisons and the 40-question answer evaluation; document actual results and remaining acceptance work.
- [x] Document each improvement separately, including API compatibility and context limits.
- [x] Request one fresh final code review, address blocking findings, and record final verification.
