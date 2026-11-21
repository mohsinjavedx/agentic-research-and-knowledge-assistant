# Step 6: Reproducible evaluation

The retrieval runner accepts explicit dataset, mode, and output paths, records the dataset SHA-256/revision and each query's rankings, and refuses to overwrite reports. From the repository root, use new output filenames:

```powershell
uv run --project apps/api python scripts/run_retrieval_eval.py --mode dense --output data/eval/new-dense-run.json
uv run --project apps/api python scripts/run_retrieval_eval.py --mode hybrid --output data/eval/new-hybrid-run.json
```

The preserved comparison reports are `retrieval-corrected-dense-2026-11-21.json` and `retrieval-corrected-hybrid-2026-11-21.json`. A nonzero exit code with a saved report means the measured acceptance gate did not pass.

For a live answer evaluation:

```powershell
uv run --project apps/api python scripts/run_grounded_qa_eval.py --output data/eval/new-answer-review.json
```

The version 2 report records all 40 outcomes, including HTTP errors, malformed HTTP 200 payloads, degraded responses, used excerpts, citations, wall-clock latency, and server timing. Failures are retained as failures and cannot count as abstentions. Request success requires an explicit HTTP 200, strict response-schema validation, no recorded error, and a non-degraded payload.

Citation validity checks source identity, source quote/ranges, and actual used context. Acceptance also requires a clean request run, at least 27/30 answerable completions, the existing 90% out-of-corpus detection, valid citations, and the separate 30-answer faithfulness audit. Old version 1 packets can be read for history but lack the evidence needed to pass the new request/context checks. Prompt-injection acceptance remains separate.

Mark `faithful` and `review_note` only after checking each claim against the cited source, including ambiguous table rows. Score a completed audit to a fresh file:

```powershell
uv run --project apps/api python scripts/run_grounded_qa_eval.py --score-audit data/eval/new-answer-review.json --output data/eval/new-answer-review-scored.json
```

During implementation the local model could not reload because Windows virtual memory was nearly exhausted. That is a live-provider failure, not evidence of improved answer quality. The final evaluation report records the actual outcome; no mock test or valid JSON schema substitutes for the live faithfulness gate.
