# Phase 4, step 3: Citation verification and abstention

The model's citations are treated as untrusted output. A generated citation names a context index, copies an actual answer claim, and includes a source quote. The service maps the index through the provider's exact used-passage list and attaches chunk/document/page metadata from retrieval. It checks that the quote occurs inside the supplied passage and returns its original normalized-chunk text and range. A valid source ID alone is insufficient.

All non-whitespace answer characters must be covered by valid citation claims, including signs, units, and punctuation. Invalid-only citations, uncovered answer text, or an explicit model insufficiency verdict discard generated prose and return an abstention. These checks establish provenance and coverage, not whether a quoted passage semantically entails a claim; faithfulness remains a separate evaluation.

Retrieval confidence is checked before invoking the LLM. If there are no results or the top cosine similarity is at or below `RETRIEVAL_SIMILARITY_THRESHOLD`, generation is skipped and the response is marked insufficient. This reuses the Phase 3 calibrated cutoff rather than introducing a second abstention rule.

## Verification

From `apps/api`:

```powershell
uv run pytest -q tests/unit/test_generation.py tests/unit/test_grounded_citations.py tests/unit/test_answer_api.py
```

Tests check out-of-range context indices, invented/out-of-context quotes, unrelated claims, uncovered answer text/symbols, Unicode source ranges, citation mapping, abstention, and that low-confidence evidence does not trigger a model call.

## Source

- [answer.py](../../../apps/api/app/services/generation/answer.py) — source-context validation and abstention behavior.
- [citations.py](../../../apps/api/app/services/generation/citations.py) — quote provenance and answer coverage.
- [test_generation.py](../../../apps/api/tests/unit/test_generation.py) — invalid-citation and insufficient-evidence cases.
