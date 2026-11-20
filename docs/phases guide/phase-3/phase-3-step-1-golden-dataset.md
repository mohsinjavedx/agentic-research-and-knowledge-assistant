# Phase 3, step 1: Golden dataset and sample corpus

The Phase 3 corpus is three small, openly licensed research papers focused on retrieval-augmented generation and knowledge retrieval. Attribution, license, source URLs, checksums, and stable document IDs are recorded in [the sample corpus manifest](../../../data/samples/manifest.json) and [sample README](../../../data/samples/README.md).

## Dataset contract

[golden_set.json](../../../data/eval/golden_set.json) contains exactly 40 questions:

- 10 single-fact lookup questions.
- 10 table lookup questions.
- 10 cross-section synthesis questions.
- 10 out-of-corpus questions with no page labels.

Every answerable item has one or more ground-truth pairs containing a stable `document_id` and a one-based PDF `page_number`. The document IDs are UUIDv5 values derived from the papers' DOIs, so re-indexing does not invalidate labels.

## Index the sample PDFs

From `apps/api`, after PostgreSQL is running and migrations are current:

```powershell
uv run alembic upgrade head
uv run python -m app.services.indexing.seed_samples
```

The seeder verifies the manifest checksums, embeds each PDF through the Phase 2 pipeline, and persists each as a global read-only sample. Re-running it skips matching indexed samples and rejects a conflicting ID/checksum rather than silently replacing data.

## Source files

| File | Purpose |
| --- | --- |
| [manifest.json](../../../data/samples/manifest.json) | License attribution, SHA-256, stable IDs, and paper metadata. |
| [golden_set.json](../../../data/eval/golden_set.json) | Fixed retrieval queries and page-level relevance labels. |
| [seed_samples.py](../../../apps/api/app/services/indexing/seed_samples.py) | Checksum-verified, resumable sample indexing. |

