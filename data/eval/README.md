# Phase 3 evaluation data

- [golden_set.json](golden_set.json) is a versioned set of 40 retrieval questions: 30 answerable questions with one-based PDF-page ground truth and 10 out-of-corpus questions.
- The answerable set is balanced across single-fact lookup, table lookup, and cross-section synthesis. Document IDs refer to the stable sample IDs in [the corpus manifest](../samples/manifest.json).
- The corpus is redistributed under CC BY 4.0; see [sample attribution and sources](../samples/README.md).

Run the evaluation after indexing the sample corpus and applying database migrations:

```powershell
cd apps/api
uv run python -m app.services.indexing.seed_samples
cd ..\..
uv run --project apps/api python scripts/run_retrieval_eval.py
```

The script reports measured retrieval metrics and the similarity cutoff calibrated on the out-of-corpus questions. It writes a new timestamped report by default, or accepts `--output <new-path>`; existing reports are never overwritten. Use `--mode dense` or `--mode hybrid` and `--dataset <path>` for explicit comparisons. Reports record a dataset hash and per-query rankings.

The active dataset has schema version 1, revision 2. `golden_set.v1.json` preserves the original bytes; `label-audit-2026-11-21.json` records the independent PDF audit and the sole required correction (education-single-01: page 8 to page 7). The original `retrieval_metrics.json` remains unchanged. Corrected comparison reports are `retrieval-corrected-dense-2026-11-21.json` and `retrieval-corrected-hybrid-2026-11-21.json`.
