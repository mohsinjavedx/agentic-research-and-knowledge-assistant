# Phase 7 completion verification

Date: 23 November 2026. Scope: user-facing Phase 7 implementation, responsive UI,
private document upload, source inspection and workflow progress. Source:
implementation guide v2.0, page 13. Earlier phase quality gates remain separate.

## Files and working flow

Frontend paths below are relative to `apps/web`; backend paths are repository-relative.

- `components/app-shell.tsx`: persistent navigation, breadcrumb and shared health.
- `components/research-workspace.tsx`: question/research modes, three starters,
  source controls, loading/cancel/error/answer states.
- `components/source-library.tsx`: visible papers and cross-route selection.
- `components/document-library.tsx`: PDF picker/drop area, validation and results.
- `components/{markdown-report,citation-drawer}.tsx`: safe Markdown, inline badges,
  native source modal, Unicode highlighting and clipboard action.
- `lib/use-research-job.ts`: sequential two-second polling and abort/wait bounds.
- `styles/{workspace,research}.css`, `app/globals.css`: responsive layout, tokens,
  effects, reduced motion and highlighting. Font/icon assets are bundled locally.
- `apps/api/app/services/indexing/{processor,upload}.py`: shared stream pipeline,
  single parser worker and stream ownership/cancellation cleanup.
- `apps/api/app/api/v1/documents.py`: private PDF upload and visible library list.
- `tests/{phase7,request-rules,proxy}.spec.ts`: UI, selection and real-proxy checks.

The default workspace embeds a question, retrieves scoped sources and presents an
answer with inspectable citations. Deep research starts a Phase 6 job; its report
page polls actual snapshots for plan/tool/evidence/report content. Uploads become
private indexed documents, automatically selected in the shared library.

## Acceptance checks

The UI regression follows first visit -> golden starter -> exact citation ->
three-document comparison -> completed report. Emoji-prefixed evidence proves
code-point highlighting; two private papers prove distinct names. Bad ranges
never receive invented highlights. Modal containment, Escape return focus,
safe Markdown, clipboard reset and source selection are checked.

Quota, OCR, stalled health, answer timeout and stalled research cases release
controls or offer retry. Tests inspect every route and the drawer at 360, 768 and 1280
pixels with reduced motion. Backend checks use real text/blank PDFs, PostgreSQL
persistence and foreign-session denial. Proxy checks forward 12 MiB and wait 35 seconds.

## Final results

- Backend: **375 passed** with `RUN_DB_TESTS=1`, including real PostgreSQL integration.
- Frontend: **16 passed** (14 browser flows/viewport checks and 2 selection-boundary tests).
- Real proxy: **2 passed**, including all 12,582,912 bytes and a 35-second upstream response.
- Frontend ESLint, TypeScript, Prettier check and production Webpack build: **pass**.
- Backend Ruff lint/format (122 files), mypy (77 source files), Alembic schema check: **pass**.
- `git diff --check`: **pass**. No commit, push or merge performed.

A real HTTP smoke through the running Next proxy returned health 200, session 204,
library 200 with 3 papers, and answer 200 with the correct five benchmark names,
no degraded/insufficient flag,1 citation and an exact original-range quote.
Evidence: [live smoke](../../../data/eval/phase7-live-smoke-2026-11-23.json).
This single live question does not establish a broader generation-quality gate.

Screenshots use deterministic mock evidence and were inspected for layout:
[desktop workspace](images/workspace-desktop.png), [mobile source drawer](images/source-mobile.png),
[tablet drawer](images/source-tablet.png), [research report](images/research-report-desktop.png).
The report fixture intentionally includes an unsafe-link sanitization probe.

The upload/list API and the four Phase 7 UX steps are implemented and verified.
No Phase 7 implementation stage remains blocked. Earlier phase quality and Phase 8/9
security/deployment evaluations remain outside this completion.

## Review and decisions

One fresh read-only senior review identified five important fixes: proxy body
limit, proxy timeout, concurrent native parsing, private source naming and inline
trigger focus. Each has a regression. Native worker tests verify serialization
and closed cancelled-queue streams. Source limits, clipboard reset and upload
copy spacing were also completed as UI polish.

Ruling: finish in the user's dirty `phase-7` checkout and preserve their Phase 6
progress changes and Phase 7 foundation. No commit, push or merge. One existing
Phase 6 test formatting issue was corrected without changing behavior. The
additional `python-multipart` dependency appeared outside this implementation
during the session and was preserved.

Ruling: add raw-PDF upload/list endpoints to complete the OCR error UX acceptance.
Reuse existing limits, parsing and session scope. No OCR engine or validation
bypass. Raw transport avoids multipart buffering; one worker owns native parsing.

Ruling: use same-origin proxying to make anonymous cookies consistent. Explicit
21 MB/190-second proxy limits accommodate the API's20 MiB limit and shorter client
deadlines. Large-file/body and delayed-upstream behavior are measured directly.

Ruling: Windows had reserved 55432, so use configurable15432 without changing
credentials or removing the database volume. Narrow the API watcher to `app/`
so it does not scan frontend build outputs.

## Limits

Browser answers/reports are fixtures, not hosted-model quality measurements.
This does not establish earlier faithfulness/recall targets, cloud deployment
readiness, or Phase 8 abuse/security acceptance. Large PDF indexing can outlast a
browser deadline; the UI offers retry/smaller input instead of infinite waiting.
Source inspection uses normalized chunk text and exact code-point ranges, not
guessed PDF page coordinates.
