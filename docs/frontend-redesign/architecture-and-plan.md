# Research Assistant frontend redesign

Source brief: user-provided master prompt, 23 November 2026. Implement in the
existing checkout, preserving all uncommitted Phase 8 work. No deployment,
commits, credential changes, database migration or backend-contract replacement.

## Audit

Next 16.4.6 App Router, React 19.3.1, strict TypeScript, native CSS, React Markdown
with GFM; React Context owns source scope/readiness, local state owns answers.
Existing paths: /, /workspace, /documents, /research, /research/[id]. Existing
components: AppShell, BackendReadinessProvider/WakeUpBanner, SourceLibraryProvider,
ResearchWorkspace, DocumentLibrary, MarkdownReport, CitationBadge/CitationDrawer,
ServiceStatus. useResearchJob polls persisted jobs with bounded timers/cancellation.
All fetches use the existing same-origin /api/v1 proxy, include credentials, parse
typed responses, and preserve timeouts/errors. Auth is an anonymous HttpOnly
session cookie; there are no account/password/login/register/logout endpoints.

PDF POST sends raw application/pdf bytes, returns only after indexing is ready.
GET documents exposes ready visible samples/current-session uploads; DELETE is
already owner-scoped but not yet wired into the UI. Filename, pages, sample flag
and ready status exist; file sizes/dates/global pending/failed counts do not.
Answer POST returns answer, citations with code-point offsets, evidence with
cosine similarity, insufficient_evidence/degraded_mode. Research POST/GET exposes
actual job progress, tools, reports and sources; no list/history/saved-report API.
Current starter buttons immediately submit; the new brief requires fill-only.
Current root is a light workspace, not a public landing page. No current theme,
collapsible sidebar, searchable document table, settings or knowledge-base page.

## Design

Dark first: canvas #0B0D12, sidebar #10131A, surface #151923, raised #1B2130,
border #292F3D, text #F1F3F9, muted #A0A8B8, accent #8B7CFF, interactive #5B9DFF.
Inter Variable is bundled locally; Lucide is the single icon library. Reuse native
CSS and accessible HTML, no animation/UI framework migration. Type: 60px marketing
headline, 30px page titles, 20px sections, 14px body, 12px metadata. 4px spacing;
12px panels, 8px controls; subtle borders and purposeful 160–220ms motion.

The distinctive feature is the evidence relationship: a quiet, readable answer
column beside inspected source passages, using the actual citation contract.
The public page shows a clearly labeled example from an included paper and the
actual two pipeline flows; no fake activity or performance numbers. The app has
a 248px sidebar (68px collapsed), 64px header and optional 340px source pane.
At narrow widths navigation becomes a keyboard-accessible modal drawer and source
inspection remains a focus-trapped native dialog. Real blank states replace stats.

## Implementation plan

- [x] Foundation: tokens, Inter/Lucide, custom connected-knowledge mark, public/app
      chrome, collapsed/mobile sidebar, preferences and shared tab-memory context.
- [x] Public landing/about: factual features, actual technology and pipeline diagrams,
      working anchor links and workspace CTAs; public routes work without backend calls.
- [x] Research: explicit submit, Enter/Shift+Enter, growing input, safe duplicate
      prevention/cancel-waiting, source scope, real response rendering, copy/save-in-tab,
      evidence explorer with exact highlights, existing research job/timeline parity.
- [x] Documents/knowledge: real GET/POST/DELETE, search/filter/scope, drag/drop upload
      with honest indeterminate indexing, ready-only metadata and confirmed deletion.
- [x] History/saved/settings: actual tab activity, explicitly in-memory/no durable
      account history, real preferences/clear controls, no fake billing or logout.
- [x] RED/GREEN behavior tests; lint/types/format/build; existing API/proxy tests;
      1440/1280/1024/768/390/360px layouts, keyboard/focus/motion/console checks.
- [x] Fresh read-only final review, verified fixes, real local smoke and documentation.

## Decisions and constraints

The user has already opted out of permission/approval pauses. This specific brief
provides the design direction; execute inline after the short plan. No worktree
switch/stash is appropriate because Phase 8 changes must remain in place.
Do not fabricate auth forms or context-aware generation: each API answer is an
independent scoped question. Recent/saved items, if added, reflect real actions
and live only in React memory for this tab, clearly disclosed; never localStorage
private documents/answers. Theme/sidebar preferences alone may use localStorage.
No fixed usage meter, invented dates/sizes, pretend percent progress, fake streaming
or server-side research-cancel controls. No unverified external portfolio links.
Backend and Phase 8 security/ownership/quota behavior stay intact.

## Review focus

- Starter selection must not submit; Enter and submit must not duplicate a request.
- Cookie/credentials, ownership, scope validation and API errors must survive UI changes.
- Unicode citation offsets must remain code-point based; incorrect ranges never highlight.
- Tab history must never be presented as durable account/server persistence; private
  response text must not be written to browser storage or analytics.
- Native dialogs/drawers restore focus, contain focus and fit 360px; mobile controls
  are reachable and reduced motion is respected. Public pages do not need a live API.
- Delete only confirmed private uploads, prune selection/history, and resist stale
  library responses. Never invent unsupported file metadata or processing statuses.

## Progress

Audit, implementation and verification completed on 23?24 November 2026.
The redesign keeps the existing same-origin API and anonymous-session contract.
No backend/Phase 8 source was changed, and all 144 protected file hashes match.

Observed RED/GREEN coverage includes fill-only starters, exact citations, native
dialogs, library mutation races, private tab activity, exports, real Retry-After,
remote Markdown image privacy, route navigation during mutations, partial-report
warnings, current-scope starters, scope reordering, resolved System appearance,
the empty-composer overlap found in final mobile visual QA, and fully visible
long quotes through both source scroll areas. Desktop source selection also
opens the correct card and preserves the conversation position.

Final validation: 47/47 browser tests against the compiled production app (2.1 minutes), 2/2 real Next proxy tests,
lint, types, formatting, production build and npm audit (zero vulnerabilities).
Six widths and all eight redesigned routes pass overflow/browser-error checks.
The final production bundle and Git history pass the configured secret scan,
including checksum, canary and injected-secret/client-copy detection guards.

One fresh read-only review was completed. All important findings were fixed and
verified; the initially minor findings were completed or resolved by disclosing the actual
cache policy, following the explicit user brief. No review fix remains deferred.

Docker was initially unavailable. On 24 November it recovered; PostgreSQL and
the unchanged API were started normally. A browser against the production Next
server then verified a real model answer naming all five benchmarks, one exact
citation, ten retrieved passages, PDF indexing (201), confirmed private deletion
(204), mobile answer layout, focus restoration and light appearance. There were
no unhandled browser errors. Final live checks also confirm that long quotes
are visibly inside both the source pane and dialog, with conversation position
preserved and Close kept accessible. Test PDFs were cleaned up, and existing documents
were preserved. See verification.md for the detailed evidence and limits.

The working changes remain uncommitted on phase-8; no deployment or push occurred.
