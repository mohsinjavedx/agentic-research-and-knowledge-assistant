# Phase 3: Retrieval and evaluation

| Step | Guide | Status |
| --- | --- | --- |
| 1 | [Golden dataset and sample corpus](phase-3-step-1-golden-dataset.md) | Implemented |
| 2 | [Session-scoped dense retrieval](phase-3-step-2-scoped-dense-retrieval.md) | Implemented |
| 3 | [Retrieval evaluation](phase-3-step-3-retrieval-evaluation.md) | Implemented; quality targets not met |
| 4 | [Similarity abstention calibration](phase-3-step-4-abstention-calibration.md) | Implemented; detection and latency targets met |

Phase 3 establishes a retrieval baseline before generation. The corpus contains three attributed CC BY 4.0 research PDFs. Its 40 fixed questions include 10 each of single-fact lookup, table lookup, and cross-section synthesis, plus 10 unanswerable questions.

The evaluation gate requires Recall@5 ≥ 0.80, Precision@5 ≥ 0.60, MRR ≥ 0.70, at least 90% out-of-corpus detection, and p95 query latency ≤ 800 ms excluding cold start. The latest run meets the out-of-corpus detection and latency targets, but not the three retrieval-quality targets; see the measured [evaluation report](../../evaluation-report.md).

Start with the [repository evaluation report](../../evaluation-report.md) for the latest measured results.
