# Step 4 — Ablation and acceptance

`scripts/run_phase5_ablation.py` runs Vector-Only, SQL Hybrid RRF, and Hybrid+TinyBERT against all40 golden questions:30 answerable and10 outside the corpus. Only30 answerable questions contribute to Recall@5/MRR; all40 contribute to timing. A fixed19-question exact-match/acronym slice was frozen from query text before hybrid/reranker measurement.

## Comparable inputs

The runner validates the corpus is indexed and records the golden SHA256/revision, ordered corpus hash (IDs, pages, normalized text, vectors), slice manifest, model revision and model checksum. Corpus and dataset are checked again after the run. Each question uses the same precomputed embedding for all variants. Labels and source documents are unchanged.

Metrics count only ranked top-five cores. Adjacent context is excluded and tested independently; it cannot make a missing ranked page count as retrieved. Per-query IDs, page ranks, cosine, fusion scores, neural scores, and applied/failure status remain in the JSON. A failed reranker falls back for diagnosis but marks the variant unavailable, so it cannot pass as a neural result.

## Gates and results

Evidence: [complete ablation](../../../data/eval/phase5-ablation-natural-2026-11-21.json), [fresh dense baseline](../../../data/eval/phase5-baseline-2026-11-21.json), and [first SQL hybrid run](../../../data/eval/phase5-sql-hybrid-2026-11-21.json).

- **Gain:** SQL Hybrid overall Recall delta0.00 percentage points, MRR delta−1.67 points. Exact-match Recall/MRR deltas0.00. Required overall gain≥5 or slice gain≥15: **fail**.
- **Recall non-regression:** Hybrid76.67% versus corrected dense76.67%; drop0.00 points≤1: **pass**.
- **SQL p95:** Hybrid17.64ms≤1200ms: **pass** on this machine.
- **Extra worker memory:** Hybrid1,945,600bytes<50,000,000bytes: **pass** for the measured worker scope. Database/container overhead was not measured, so deployment-wide acceptance remains unverified.
- **Optional neural variant:** Recall78.33%, MRR0.5694; quality gain fails. SQL p95~115.29ms, reranking p95~385.62ms, extra worker RSS72,380,416bytes. It is implemented but not selected as the default.

The historical Phase3 published report uses the original labels: Recall76.67%, MRR0.6022. The corrected current dense baseline has MRR0.6244. The stricter comparable corrected baseline governs adoption; neither comparison supplies the required SQL Hybrid gain.

Two generic OR-query experiments were retained in `data/eval/phase5-lexical-policy-experiments-2026-11-21.json`. All-term OR reached MRR0.6772; removing generic question terms reached0.6678. Both reduced Recall@5 to73.33% and failed the recall-loss limit. These query policies were rejected. Production preserves natural `websearch_to_tsquery` semantics, including quoted phrases and negation. No question-ID exceptions or label changes were used.

## Measurement limits

SQL timing is the client-observed database roundtrip plus ORM hydration and excludes embedding and generation. Models/connections are warmed for latency; first reranker load/inference is reported separately. RSS is current process working-set memory sampled every5ms after warm BGE/dense retrieval, including cold reranker allocations for the neural variant. The <50MB check uses decimal bytes. This is a sampled development-worker measurement, not a profiler proof of every transient allocation, PostgreSQL backend memory measurement, or512MB production deployment validation.

These are fixed development-set comparisons. Further lexical candidate/ranking improvements require a separate iteration and validation before enabling hybrid by default. A larger model should likewise be compared rather than assumed better.

## Verification

Gate tests cover percentage-point thresholds, equality boundaries, recall regressions, strict memory limits, missing measurements, unavailable variants, and exclusion of extra context from ranking metrics. The CLI refuses to overwrite reports before touching the database. A successful execution of the ablation can still exit1 because measured acceptance failed; the preserved JSON distinguishes this from a runtime error.
