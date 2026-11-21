# Step 2: Scoped hybrid retrieval

`app/services/retrieval/hybrid.py` combines up to 20 cosine-nearest chunks and 20 PostgreSQL full-text matches. The keyword branch uses the existing generated `fts_tokens` column and GIN index, `websearch_to_tsquery`, and `ts_rank_cd`; it is not BM25. Question tokens are combined with OR for candidate recall and passed as a bound SQL parameter.

Both branches receive the same allowed document IDs after the route's session/sample/expiry resolution. Foreign or explicitly unavailable document IDs retain the existing 404 behavior. PostgreSQL integration tests verify vector/keyword ranking and foreign-document exclusion in both modes.

Results are deduplicated by chunk ID and combined using reciprocal rank fusion with constant 60. A branch contributes at most one vote per chunk. Ties use best rank and stable chunk ID. `fusion_score` is separate from the original `cosine_similarity`; neither should be presented as answer confidence. Abstention checks the maximum returned cosine, since fusion order need not be cosine order.

Configuration:

```dotenv
RETRIEVAL_MODE=dense
```

Set `hybrid` to evaluate the combined strategy. Dense remains the measured default: corrected dense Recall@5/Precision@5/MRR are 0.7667/0.3000/0.6244; hybrid results are 0.7500/0.2800/0.7250. Measured warm retrieval p95 was 45.21 ms and 121.64 ms respectively. These are fixed-set observations, not a held-out generalization result. Both modes still fail the complete retrieval acceptance gate.

The shared dispatcher is `app/services/retrieval/search.py`; both `/search` and `/answer` use it. No migration or reindex is necessary.
