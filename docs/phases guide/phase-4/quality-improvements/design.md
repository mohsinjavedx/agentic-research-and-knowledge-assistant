# Answer quality improvements

Approved direction: the user's instruction to start implementation follows the six-part recommendation in the conversation.

Keep the pinned BGE embedding model and local Ollama model. Improve the existing PostgreSQL retrieval and generation pipeline, preserving session isolation, evidence provenance, and safe failure behavior.

## Approaches

Prompt-only changes improve presentation but cannot address retrieval noise. Larger embeddings and a cross-encoder were already tested without meeting all quality/latency gates. The selected approach combines the existing vector and full-text indexes, extracts focused source passages, and checks citation quotes and answer coverage.

## Behavior

1. Audit the 30 answerable labels directly against the source PDFs; preserve the original dataset/report. Keep the 10 out-of-corpus questions unchanged. Record source excerpts and reasons for label changes rather than tuning labels to rankings.
2. Compare dense retrieval with hybrid retrieval: up to 20 candidates per method, same allowed document IDs in both branches, deduplicate by chunk ID, combine ranks using reciprocal rank fusion (constant 60). Keep cosine similarity distinct from fusion scores. Select the production default from measured results, not assumptions.
3. Select complete Markdown paragraphs/lists/tables with their source offsets; favor question-bearing content and fit the local context without cutting facts, qualifiers, lists, or table rows. Keep full retrieved evidence available.
4. Generate concise prose. Each citation must repeat an actual claim from the answer and quote the supplied source passage. Validate quote provenance, source indices, and coverage of answer text. These checks establish traceability, not semantic entailment; assess support separately.
5. Add `used_evidence` to the HTTP response, with the exact excerpts, original retrieval indices, context indices, and character ranges within the normalized retrieved chunk. Preserve existing `evidence` and response flags.
6. Run corrected dense/hybrid comparisons, real answer smoke cases, and the 40-question answer evaluation. Report failures and abstentions rather than hiding them. Keep the human faithfulness and live-injection acceptance gates explicit.

## Constraints

- Work in the existing `phase-4` branch; preserve all pending user changes. Do not commit, stage, merge, or push the user's work.
- No new hosted services, model downloads, database schema changes, or embedding reindex are needed for this iteration.
- Both retrieval paths must obey existing sample/current-session/expiry visibility rules.
- Do not fabricate citations during timeout or rate-limit fallback; malformed generation stays a sanitized failure.
- Do not increase context or similarity thresholds blindly. Preserve prior evaluation files and record dataset hashes in new reports.
- Documentation follows the existing phase folders, one guide per improvement step.
