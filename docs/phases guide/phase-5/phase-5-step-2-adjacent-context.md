# Step 2 — Adjacent chunk context

Implemented in `apps/api/app/services/retrieval/context.py` and connected to `/search` and `/answer`.

For each ranked hit above the existing calibrated cosine threshold, fetch index−1 and index+1 from the same allowed document. A neighbor must also exceed that threshold and be no more than `ADJACENCY_SIMILARITY_MARGIN=0.05` below the anchor. Keep at most `MAX_ADJACENT_CHUNKS=5` extra records in total. Connected adjacent pairs become one logical context group; duplicate neighbors appear once.

`ENABLE_CONTEXT_EXPANSION=true` enables this behavior. Set it false to compare ranking without expansion. The SQL always repeats the allowed document filter; API visibility still requires a ready sample or an unexpired document owned by the current session.

Model input limits still apply. Shared generation context packing selects whole context groups and can skip a later group that cannot fit. Hosted input has a configurable conservative estimated budget (`HOSTED_LLM_INPUT_TOKEN_BUDGET=6000`); local input reserves the configured output allowance. No member is clipped or silently reported as used if omitted. This prevents the default top-five request plus expanded sources from overflowing the tested Groq input limit.

## Source identity and citations

Merging is logical: each member retains its original text, chunk ID, document ID, page, and cosine. The generation prompt places the full members together in document order inside a `context-group`, with a separate evidence index for each member. Passage focusing does not cut these members again. The existing citation verifier checks a quote against one original chunk and its exact character range.

Search `results` contains only the ranked top-k. `adjacent_context` contains extra source records. `context_groups` describes ordered membership. Answers return the whole source pool in `evidence`, core IDs in `ranked_chunk_ids`, and the actual model passages in `used_evidence`. An added neighbor is marked `is_adjacent_context=true`. Extra context never counts as a top-five ranking hit in evaluation.

## Verification

The PostgreSQL test exercises both directions, first/last chunk boundaries, same-document isolation, score rejection, duplicate suppression, and rejection of an anchor outside the allowed scope. The prompt test checks original full text, ordering across pages, and retained retrieval indices. Existing answer tests continue to verify exact source quotes and offsets.

Step-2 full backend/database suite: **255 passed**. Ruff imports/format and mypy pass. Additional final API and citation smoke results are recorded in the Phase 5 README.
