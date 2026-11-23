# Phase 7, step 2: Zero-friction sample workspace

The workspace preselects the three Phase 3 sample papers and offers two
single-paper starter questions from the golden set plus a multi-paper comparison.
Answer prompts call `POST /api/v1/answer`; the comparison starts a Phase 6
research job. The selected document IDs and question are sent explicitly, and
the normal question form remains available.

The sample papers must already be indexed in the API database. Follow the
root README's Phase 3 seeding instructions before trying the live workspace.
The Paper library now accepts private searchable PDFs through the session-scoped
upload API. Successful uploads appear in the shared library and are selected
for the workspace. Samples remain usable without uploading a file.

## Visual verification

1. Open `/workspace` with a ready API. Confirm all three sample papers are
   selected and the starter prompts are enabled.
2. Select **Educational QA benchmarks**. Confirm the request uses the exact
   Phase 3 golden question and only the educational QA document ID.
3. Select **Compare the three papers**. Confirm it submits the comparison query
   with all three sample document IDs and opens the returned research job.
4. Repeat with a delayed or unavailable health response. Actions should remain
   disabled until readiness succeeds, and the wake-up banner should offer retry
   when the service is unavailable.

## Verification status

The mocked browser workflow verifies the starter-question payload and the
three-document job payload without making a live model request. The API graph
suite exercises the fixed 40-question golden set; the database job integration
test covers the multi-document job contract. See [step 4](phase-7-step-4-live-timeline.md)
for the exact commands and observed results.

## Completion changes

The root page opens the usable workspace directly. Shared source selection survives
navigation. Quick answer and Deep research have separate controls, source-count
limits (50/10), loading/cancel/error states and deadlines. Changing the source
scope hides an older answer. A delayed library read cannot discard a newer upload.
The library handles extension, size, OCR, quota and indexing errors. See
[verification](verification.md) for the final results.
