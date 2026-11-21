# Phase 4: Grounded answer generation

| Step | Guide | Status |
| --- | --- | --- |
| 1 | [Prompt isolation](phase-4-step-1-prompt-isolation.md) | Implemented; prompt-encoding tests pass; live-model injection test pending |
| 2 | [Structured answer generation](phase-4-step-2-structured-generation.md) | Native Ollama / hosted Instructor with Pydantic; one real local query verified |
| 3 | [Citation verification and abstention](phase-4-step-3-citation-verification.md) | Implemented and unit-tested; full answer-set evaluation pending |
| 4 | [Evidence fallback and evaluation](phase-4-step-4-fallback-evaluation.md) | Implemented and unit-tested; 30-answer manual audit pending |

Phase 4 adds `POST /api/v1/answer`. It uses the Phase 3 session/document scope and retrieval results, requests schema-constrained claims from native local Ollama or an OpenAI-compatible hosted model, and returns only citations whose chunk ID, document ID, and page match the retrieved context. Weak retrieval abstains without calling the LLM. Timeout and HTTP 429 responses degrade to retrieved evidence; other provider failures return a sanitized HTTP 503.

The implementation is covered by deterministic unit/API tests. A reported five-benchmark query was verified against the running API and local `llama3.2:3b` on 21 November 2026, returning the correct names and a page 7 citation. That single diagnostic does not establish full answer quality. The manual faithfulness gate and live prompt-injection gate are **not yet measured**, and Phase 4 must not be reported as acceptance-complete.

Use the [evaluation report](../../evaluation-report.md) for verified test results and the remaining acceptance work. Run the API against a configured Ollama model or an approved OpenAI-compatible hosted endpoint, then follow [step 4](phase-4-step-4-fallback-evaluation.md) to create and score the 40-question report and 30-answer manual audit.

The [six quality improvement guides](quality-improvements/README.md) document the subsequent source-label audit, optional hybrid retrieval, focused passages, checked source quotes, exact used-context reporting, and non-vacuous evaluation. The earlier successful local query is a historical smoke result; current live quality must be assessed with the updated evaluator and context/citation contract.
