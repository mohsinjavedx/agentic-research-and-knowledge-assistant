# Phase 5, step 1: SQL hybrid RRF

Production fusion now runs in one PostgreSQL statement: scoped vector/lexical top20 CTEs, independent row-number ranks, UNION ALL votes, grouped score sums, and final top-k hydration. The reciprocal-rank constant is60. Stable best-rank/UUID ties and separate cosine/fusion scores are preserved.

The lexical query uses natural `websearch_to_tsquery` semantics, including quoted phrases and negation. It no longer strips operators and rewrites every token into an OR expression. Both candidate branches filter by the same allowed document IDs before ranking. An empty lexical branch falls back to vector-ranked votes.

Verification: two new integration tests were observed failing before implementation (two SQL roundtrips and lost negation). The subsequent PostgreSQL/pure-fusion run passed **8 tests**. Ruff and mypy passed. The full starting backend/database suite passed251 tests.

The preserved initial dense and SQL hybrid reports are `data/eval/phase5-baseline-2026-11-21.json` and `data/eval/phase5-sql-hybrid-2026-11-21.json`. Dense Recall@5/MRR: .7667/.6244. Initial SQL hybrid: .7667/.6078, with warm end-to-end retrieval p95 approximately94ms. There is no recall regression, but this initial configuration does not meet the measured-gain criterion. Final SQL-only latency, memory, and three-mode ablation are evaluated in step4; this first run is not a Phase5 acceptance pass.

Source: `apps/api/app/services/retrieval/hybrid.py`. No database migration or reindex is needed.
