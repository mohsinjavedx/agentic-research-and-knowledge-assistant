# Answer quality improvements

This work extends the Phase 4 answer endpoint with measured retrieval options, focused source excerpts, quote provenance, and explicit context reporting. It retains the existing embedding/model identities and document access boundaries.

1. [Audit evaluation labels](step-1-label-audit.md)
2. [Compare dense and hybrid retrieval](step-2-hybrid-retrieval.md)
3. [Select focused evidence](step-3-focused-evidence.md)
4. [Check answer claims and source quotes](step-4-citation-support.md)
5. [Inspect retrieved versus used evidence](step-5-used-evidence.md)
6. [Run reproducible quality evaluations](step-6-evaluation.md)

Current generator configuration: [Groq `openai/gpt-oss-120b`](groq-hosted-generation.md), with verified live pilot results. The original benchmark-list request now returns a correct cited answer. A synthesis pilot still abstains; full quality acceptance remains pending.

The [design](design.md), [implementation plan](implementation-plan.md), and [progress record](progress.md) describe scope and verification. No embedding reindex or database migration is required.

Dense retrieval remains the default. On the corrected fixed dataset, hybrid improves first-relevant-result ranking but reduces Recall@5 and Precision@5, so it is available through `RETRIEVAL_MODE=hybrid` for further evaluation. Neither retrieval mode meets the complete quality gate. Source traceability checks do not establish semantic entailment; the full faithfulness audit remains separate.
