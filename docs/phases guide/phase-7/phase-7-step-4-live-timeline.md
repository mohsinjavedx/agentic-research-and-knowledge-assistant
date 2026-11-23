# Phase 7, step 4: Live research timeline

The research page polls `GET /api/v1/research/{job_id}` every two seconds while
a job is queued or running. It displays completed workflow steps, tool calls
and their result summaries, retrieved evidence, then the final Markdown report
and verified citations. The API now persists tool-call and evidence snapshots
after each completed graph node so polling can show progress before completion.

## Visual verification

1. From `/workspace`, choose **Compare the three papers**.
2. Confirm the job page shows its status, plan/steps, tool calls, and source
   evidence as the API reports them.
3. Wait for completion and inspect the report and its citation drawer.
4. Check the job response in Swagger at
   `GET /api/v1/research/{job_id}` to compare the persisted snapshot with the UI.

## Automated and browser checks

From `apps/api`:

```powershell
$env:RUN_DB_TESTS = "1"
uv run pytest -q tests/unit/test_research_graph.py tests/integration/test_research_jobs_api.py
```

The fixed golden questions are exercised by the graph test suite. The database
integration test covers queued-job creation, the completed job contract,
persisted steps/tool calls/evidence, citations, and session ownership. These
deterministic tests do not make a paid/live model request or establish the
separate Phase 6 multi-document quality gate.

The browser check uses a mocked API response that transitions from running to
completed. It verifies the answer-to-citation flow, all three sample IDs on the
comparison request, two-second polling, and rendering of each timeline section.
At 360px, 768px, and 1280px the workspace and job page must have no horizontal
overflow.

Observed results: **50 API tests passed** (including the fixed golden-question
graph suite and PostgreSQL research-job integration). Frontend ESLint,
TypeScript type-check, and production build passed. The browser check sent the
exact educational golden question and document ID, opened the highlighted
citation, then polled the three-document job twice through completion. Both
pages had no horizontal overflow at 360px, 1280px, and around the 768px
breakpoint (the browser adapter reported 767px and 769px for viewport requests
of 768px). The test exposed a 3px mobile header overflow, which was corrected
before the final build/check.

## Acceptance status

The50-test result above describes the earlier implementation. Completion results
are in [verification.md](verification.md). OCR rejection is now tested using an
actual blank PDF through the new upload API, plus the browser error flow.

The finished run page places the report beside real plan/progress, tool arguments
and results, and collected sources. Polls are scheduled two seconds after the
previous response. Requests abort on unmount and have a 15-second deadline;
a queued/running run stops automatic waiting after 10 minutes and offers retry.
Terminal jobs do not keep polling. Missing steps and progress percentages are
never fabricated.
