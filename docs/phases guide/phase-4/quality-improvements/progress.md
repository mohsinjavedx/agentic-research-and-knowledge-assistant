# Implementation progress — answer quality improvements

Plan: [implementation-plan.md](implementation-plan.md). Spec: [design.md](design.md).

Execution: in-place on the existing phase-4 branch, as authorized. User changes are preserved; no automatic commits or staging. PowerShell verification commands and this ledger replace the POSIX helper scripts on this Windows workspace.

- Task 1: complete. All 30 answerable questions audited against source PDFs; only education-single-01 changed from page 8 to page 7. Original golden_set.v1.json and retrieval_metrics.json preserved. Audit in data/eval/label-audit-2026-11-21.json; runner regression tests 2 passed. Corrected dense report saved as retrieval-corrected-dense-2026-11-21.json (quality gate still fails).
- Task 2: implemented and verified. Focused retrieval/API/generation run with real PostgreSQL: 23 passed. Hybrid report saved as retrieval-corrected-hybrid-2026-11-21.json. Dense Recall .7667 / Precision .30 / MRR .6244; hybrid .75 / .28 / .725. Keep dense default because hybrid reduced recall/precision; hybrid is opt-in.
- Task 3: implementation complete; deterministic verification passed. Quote provenance, actual used context, claim alignment, strict non-whitespace coverage, complete loose lists, and Unicode/source mappings are tested. Final reviewer findings were reproduced RED, fixed GREEN, and included in the complete suite. The live exact-query retest returned HTTP503 during model-loading allocation failure; its new answer/quote quality is unverified.
- Task 4: implementation/evaluation complete; live quality gate failed. Final full suite with RUN_DB_TESTS=1: 251 passed. Ruff/backend/script formatting and mypy65 passed. All40 live outcomes recorded in answer-quality-review-2026-11-21.json:31 HTTP503 failures,9 correct abstentions,0/30 usable answers, no generated citations, manual audit unset. The initial resource-sensitive recovery timeout passed in the final full run with its original limit unchanged. Ollama could not reload with about786MB free virtual memory; no quality success claimed.

Final review: three Important findings fixed by RED→GREEN regressions (loose lists, numeric/sign coverage, malformed HTTP200 accounting); full suite251 passed. The minor provider docstring was updated in the documentation task. Semantic entailment remains the planned separate audit; runtime capacity prevents live model verification; the PDF audit's sole correction was independently checked against the source and its file hashes were verified.

Remaining external verification: rerun the exact query and the live40-question evaluator after sufficient local virtual memory is available; review30 generated answers and perform the live injection case. Dense stays default; adopting hybrid remains contingent on better measured recall/precision. Neither quality gate is declared passed.

## Live retry after the user freed memory

The same 40-question evaluation completed with about6.5GB free virtual memory before model loading. New report: `data/eval/answer-quality-review-2026-11-21-retry-1.json`; dataset hash unchanged, no code/settings edits during the retry.

Result:40 HTTP200,0 recorded errors,0 degraded responses;1/30 cited answerable completions,29 answerable abstentions,10/10 correct out-of-corpus abstentions. The only cited answer was spot-checked and is incorrect: it reports E-EVAL count4 using section heading4.3, whereas the source states4,351. That correct value was retrieved but omitted from used context. Provenance checks passed for that citation but do not prove semantic support. All30 formal human-audit verdicts remain unset.

The runtime memory block is cleared for this run. Overall quality acceptance still fails. Further work is required on answer-bearing context selection and semantic claim support; the benchmark-list question also still abstained despite its used excerpt containing the answer. Do not mark live quote/answer quality verified merely because all HTTP requests succeeded. The earlier report is preserved unchanged.

## Groq generation switch

User authorized `openai/gpt-oss-120b` on Groq. Existing key verified; `.env` now selects hosted generation and the correct Groq endpoint/model. Backend reloaded, health confirms hosted. No application-code or grounding-rule changes were needed; `.env.example` and startup documentation now reflect Groq.

Five live pilot cases completed: benchmark-list answer correct with page7 quote in3.15s; E-EVAL count4,351 correct with quote in1.39s; table accuracy93.2% correct with quote in1.54s; comparison still abstained; out-of-corpus correctly abstained. Raw reports preserved under data/eval/groq-gpt-oss-120b-*.json. The earlier failed local reports remain intact. Full40 hosted evaluation and30-answer manual audit remain pending; no overall acceptance pass claimed.
