# Redesign verification

Final verification: 24 November 2026 (Asia/Karachi); implementation and browser runs span 23?24 November.

## Automated checks

Commands run from `apps/web`:

```powershell
npm run lint
npm run typecheck
npm run format:check
npm run test:e2e
npm run test:proxy
npm run build
npm audit
```

From the repository root, after a production build:

```powershell
python scripts/scan_secrets.py
```

The final complete redesign suite passed 47/47 browser tests against the frozen production build. Release
verification and fresh-review findings are recorded below.
Fixtures replace APIs only within Playwright tests. Production UI requests retain
the actual same-origin API and session/ownership contract. The final suite was run against
the compiled production server with no live code edits. Browser tests do not
measure model accuracy or assert that a model will always answer correctly.

## What the tests exercise

- Public pages render without API requests; actual links and workspace entry work.
- Starter selection fills only, explicit Enter sends once, scope limits remain intact.
- Real response shape, safe Markdown, small inline reference numbers, Unicode
  exact highlights, mismatched-range fallback and citation focus restoration.
- Readiness delays, dead health checks, answer/research timeouts, OCR failures,
  quotas and real Retry-After feedback leave useful recovery paths.
- Owned document deletion requires confirmation; stale reads cannot remove a new
  upload or resurrect a deletion; unrelated deletion preserves an active answer.
- Native Browse files opens a real file chooser; indexing success updates the library.
- Actual tab activity/bookmarks clear on reload; private response text is not stored.
- Insufficient evidence is not labeled as a cited answer in history.
- Markdown report export includes actual source quotes and page references.
- Sidebar collapse, mobile navigation/source dialogs, Escape, focus, theme persistence
  and light-secondary-button text contrast.
- Eight routes at 1440, 1280, 1024, 768, 390 and 360px: no horizontal overflow or
  unhandled page errors; reduced motion enabled. Existing job/source-drawer tests
  also cover 360, 768 and 1280px.

## Visual inspection

Before/after captures and responsive screenshots are local ignored artifacts in
`tmp/redesign/`. Reviewed desktop landing/workspace/documents/About and mobile
workspace/documents. Visual QA identified tiny mobile labels; these were enlarged
and mobile cards changed to a single column before release verification.

## Backend preservation

The redesign was built on the existing dirty `phase-8` branch without switching,
stashing or committing the user's work. A SHA-256 snapshot of 144 backend and
Phase 8 files was recorded before frontend edits (`tmp/redesign-protected-files.json`).
The final check confirms that all 144 protected file hashes still match. Phase 8's earlier 412-test
backend run is separate evidence; it is not represented as a new frontend run.

## Live local checks

A real-browser smoke script is prepared at `tmp/redesign-live.mjs`. It asks the
included educational-QA question through the actual proxy, inspects the returned
quote, uploads one temporary nonpersonal one-page PDF, and confirms its deletion.
It never uses production mock routes or alters existing uploads. The local Docker
engine initially reported `starting` and the API returned database-unavailable 503. On 24 November Docker and PostgreSQL recovered. The final live run used the
production Next server and real API: readiness 200, session 204, answer 200,
indexed PDF 201, owner-scoped confirmed deletion 204. The answer named all five
benchmarks, returned one citation and ten retrieved passages, and opened an exact
quote highlight. Focus restoration, mobile answer layout and light appearance
were also checked; no unhandled browser errors occurred. Evidence is in
`tmp/redesign/live-summary.json` and the corresponding `live-*.png` screenshots.

The first live harness run hit a Chrome inspector response-body eviction after
a successful upload. It was corrected to confirm the uploaded document through
the ordinary library API. Benchmark-name assertions normalize punctuation (for
example E_EVAL versus E-EVAL). The one orphaned test fixture from that attempt
was identified by exact filename, SHA-256 checksum, one-page count and creation
window, then removed in a guarded single-row cleanup. The final run uses a unique
test filename and deletes it through the UI; fallback cleanup is restricted to
that known file in its own session. No existing user document was altered. Live checks used the normal rate limits;
their request counters were not reset.

## Fresh review and regression fixes

One fresh read-only review found four important issues. Each was reproduced in a
failing browser test, then fixed in one review-fix pass:

- Generated Markdown images now render alternate text without fetching external
  resources. The privacy test observes zero tracker requests.
- Confirmed upload/deletion work lives in the persistent library provider.
  Navigation no longer aborts the operation; successful deletion prunes related
  snapshots, and uncertain failures/route entry reconcile the authoritative list.
- Copied/downloaded partial reports include the same coverage qualification as
  the displayed report, followed by actual citation references.
- Four general starter cards preserve the current document scope. Sample-specific
  demonstrations are retained in a separate, explicit disclosure.

Two additional findings were regraded as important because they affect working
controls and answer visibility: scope identity now compares document membership,
and the header theme action follows resolved System appearance. Both tests were
observed failing before their fixes. The seven review regression tests pass.
Final visual QA found the empty composer covering the sample-example disclosure.
An additional hit-target regression was observed failing, then passed after the
empty composer stayed in normal flow; answered conversations retain sticky input.
A further long-source regression checks every clipping ancestor, not just the
quote's presence or its outer-pane rectangle. It reproduced hidden highlights in
both the source dialog and pane. The pane now uses a single scroll container,
and opening the dialog scrolls both its text area and outer frame to the quote,
with a sticky header keeping Close reachable. Both failures passed
after the fix. The final production suite includes collapse/reopen, fonts/layout
settling and screenshot-capture checks for source visibility.

Final comparison with the user's explicit brief completed the remaining alignment
items: empty/whitespace drafts disable Send, and desktop citation clicks reopen
the source pane, select the matching card, highlight the exact quote, and scroll
only that pane while preserving the conversation position. The dialog and mobile
focus behavior remain available. Both missing behaviors were reproduced before
the changes. The cold-start regression now uses a valid draft so its assertion
isolates service readiness rather than the empty-input guard.

Saved research now explicitly discloses the 32-item shared tab cache and its
possible eviction of older bookmarks. This is the actual bounded in-memory
policy; it does not promise durable or unlimited bookmarks. The review findings
have no intentionally deferred UI fix remaining.

Final: Ruling: the user's explicit composer/source-panel requirements take
precedence over initially classifying these as minor refinements. Both behaviors
were completed and tested; the existing cache policy is disclosed directly in
Saved. Cost: additional frontend selection state, covered by focused regressions.

Final: Ruling: account/password/OAuth, durable history, streaming and staged
progress remain absent because the existing backend has no such contract. Cost:
users keep anonymous-session access and tab-only history until backend support exists.

Final: Ruling: the initial Docker outage was treated as a runtime prerequisite;
API readiness and model validation were not weakened to hide it. Once Docker
recovered, the actual production UI/API smoke passed. Cost: the application still
requires its configured PostgreSQL/API services; successful offline generation
is not implied. The earlier live-verification block is resolved.

Final: Ruling: preexisting Phase 8 backend work stays outside the frontend review.
Cost: this task relies on its earlier backend verification; protected hashes are
checked to establish that frontend edits did not alter that implementation.

Automatic approval review rejected removal of empty screenshot-artifact folders
outside the workspace with “blocked by policy.” They were left in place; no
alternate deletion mechanism was used.

## Final results

- 47/47 browser tests passed against the compiled production app (2.1 minutes), including all review and visual regressions.
- 2/2 real Next rewrite tests passed: PDF larger than 10 MiB and a 35-second upstream response.
- ESLint, TypeScript, Prettier check and production build passed.
- npm audit reported zero vulnerabilities, including development dependencies.
- Gitleaks 8.30.1 passed Git-history and final production-bundle scans with zero
  findings; release checksum, canary, injected manifest secret and client-copy
  checks passed. The configured Phase 8 scanner was preserved.
- Real production-server browser smoke passed: answer, five benchmark identities,
  exact quote highlight, owned upload/indexing, confirmed deletion and light theme.
  A separate final live check covers empty-draft guards, desktop source selection,
  actual quote visibility through all clipping ancestors in both dialog and pane,
  conversation position, empty/whitespace draft guards and the Saved capacity notice.
  The final live run returned true for every assertion, including visibility after
  layout/screenshot capture, and recorded no unhandled browser errors.
- All 144 protected backend/Phase 8 files are unchanged.
- Changes remain uncommitted on the existing phase-8 branch; nothing was published.

Local logs are ignored artifacts under tmp: redesign-final-{lint,types,
format-check,e2e,build,secret-scan}.txt, redesign-release-proxy.txt and
redesign-live-run.txt and redesign-source-live-run.txt. The tracked/unignored working-file scan also passed with zero findings (358 files).
