# Phase guides

Each guide records the delivered changes, source structure, runtime behavior, run commands, and verification status for one implementation phase.

| Phase | Folder and index |
| --- | --- |
| 0 | [Project foundation](phase-0/README.md) |
| 1 | [Document ingestion and chunking](phase-1/README.md) |

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
```

The Phase 0 guide records the foundation. All six Phase 1 implementation steps now have guides. The representative-corpus parsing and text-retention acceptance benchmark remains pending.
