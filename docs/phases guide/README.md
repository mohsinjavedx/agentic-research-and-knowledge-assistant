# Phase guides

Each guide records the delivered changes, source structure, runtime behavior, run commands, and verification status for one implementation phase.

| Phase | Folder and index |
| --- | --- |
| 0 | [Project foundation](phase-0/README.md) |
| 1 | [Document ingestion and chunking](phase-1/README.md) |
| 2 | [Embeddings and unified indexing](phase-2/README.md) |
| 3 | [Retrieval and evaluation](phase-3/README.md) |

Each phase has its own folder and README. Individual step guides live inside that phase folder.

```text
phases guide/
|-- README.md
|-- phase-0/
|   |-- README.md
|   `-- phase-0-project-foundation.md
`-- phase-1/
    |-- README.md
    |-- phase-1-step-1-pdf-validation.md
    |-- phase-1-step-2-layout-aware-extraction.md
    |-- phase-1-step-3-scanned-pdf-detection.md
    |-- phase-1-step-4-deterministic-normalization.md
    |-- phase-1-step-5-markdown-aware-chunking.md
    `-- phase-1-step-6-crash-safe-recovery.md
|-- phase-2/
    |-- README.md
    |-- phase-2-step-1-embedding-providers.md
    |-- phase-2-step-2-batch-metadata.md
    |-- phase-2-step-3-vector-fts-indexes.md
    |-- phase-2-step-4-session-idempotency-deletion.md
    `-- phase-2-step-5-expired-session-cleanup.md
|-- phase-3/
    |-- README.md
    |-- phase-3-step-1-golden-dataset.md
    |-- phase-3-step-2-scoped-dense-retrieval.md
    |-- phase-3-step-3-retrieval-evaluation.md
    `-- phase-3-step-4-abstention-calibration.md
```

The Phase 0 guide records the foundation. All six Phase 1 implementation steps now have guides. The representative-corpus parsing and text-retention acceptance benchmark remains pending.

The Phase 2 folder documents all five steps. Steps 1–2 and 4–5 are implemented. Step 3 includes the database migration, persistence service, and local PDF indexing CLI. A public upload/retrieval workflow and the full end-to-end Phase 2 acceptance gate remain outstanding.

Phase 3 adds an attributed CC BY 4.0 sample corpus, a page-grounded 40-question evaluation set, session-scoped dense search, and a reproducible metric/calibration runner. See its guide for measured acceptance status.
