# Step 4: Claims and source quotes

Generated citations now contain `claim`, zero-based `evidence_index`, and `quote`. The prompt asks for concise prose, a citation claim copied from the actual answer, and an exact supporting source quote. A list answer must explicitly name its items and quote the supporting list.

`app/services/generation/citations.py` checks:

- The index identifies a passage actually supplied to generation.
- The claim occurs in the answer after whitespace normalization.
- The quote occurs inside that supplied passage; a quote elsewhere in the same chunk is insufficient.
- The returned quote maps back to the original normalized chunk. Whitespace folding and escaped prompt entities are handled without rewriting the returned source text.
- All non-whitespace answer characters are covered by valid claims, including signs, comparisons, currency, percentage symbols, and punctuation. A claim of `5%` cannot support an answer of `−5%`.

Public citations add `quote`, `quote_start`, and `quote_end` alongside the existing claim/chunk/document/page fields. The quote and offsets always reference the original retrieved text, not a generated paraphrase.

An invalid or incomplete citation set causes an abstention. An explicit model insufficiency verdict also abstains. Timeout/429 retains evidence-only degraded behavior; malformed provider output remains a sanitized HTTP 503.

These checks prove source provenance and answer coverage. They do not prove semantic entailment: a real quote can still be irrelevant to a claim, and qualifiers can be misunderstood. That remains part of the separate faithfulness evaluation.
