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

The script reports measured retrieval metrics and the similarity cutoff calibrated on the out-of-corpus questions. It writes the report to `data/eval/retrieval_metrics.json`; do not hand-edit measured results.
