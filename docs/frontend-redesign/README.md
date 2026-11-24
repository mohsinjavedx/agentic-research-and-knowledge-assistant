# Frontend redesign

The existing Next.js app now has a public product site and a dark-first research
workspace. The API, document ownership, anonymous session, rate limits and Phase 8
security code are preserved. See [the plan](architecture-and-plan.md) and
[verification](verification.md) for scope and test evidence.

## Run and explore

Start PostgreSQL and the API using the root `runGuide.txt`, then run:

```powershell
cd "C:\MOHSIN\LLM projects\New folder\apps\web"
npm ci
npm run dev
```

Open <http://localhost:3000>. The public landing and About pages work without a
backend. Research and document features require a healthy API and indexed papers.
The existing same-origin `/api/v1` proxy sends requests to the configured API;
the browser never needs a provider API key.

- `/`: product introduction, labeled example, features, pipeline, technology and links.
- `/workspace`: scoped questions, real answers, numbered citations and source explorer.
- `/research`: start a multi-document agentic research run.
- `/research/[id]`: actual job status, tool calls, report, evidence and Markdown export.
- `/documents`: search, filter, select, inspect, upload and delete owned private PDFs.
- `/knowledge`: searchable indexed knowledge and selection for the next question.
- `/history`: answers and research starts recorded by actual actions in this tab.
- `/saved`: answers/research bookmarked in this tab.
- `/settings`: theme, sidebar, session/privacy information and clear tab activity.
- `/about`: implemented architecture, evaluation definitions and repository documentation.

## Using the workspace

1. Select ready papers from Sources or the document library. Starter cards use
   your current scope and fill the question; they do not send it. The separate
   Included-paper examples disclosure explicitly switches to its sample papers.
2. Enter a question; Send stays disabled for empty or whitespace-only drafts.
   Press Enter or Ask papers. Shift+Enter adds a line. The composer prevents
   duplicate submissions and shows actual waiting/error states.
3. Read the Markdown answer. Insufficient evidence and degraded results are
   explicitly labeled. A retrieval similarity score is not answer confidence.
4. Hover a numbered citation to see source/page/excerpt metadata, or click it to
   reveal and select its source in the desktop pane, scroll that pane to the
   supporting passage, and open source details. The conversation stays in place.
   The source pane has one scroll area, and source details scroll to the quote
   with a persistent Close control. A highlight appears only when the returned Unicode
   code-point offsets exactly match the supporting quote.
5. Copy the answer, save it for this tab, or open another scoped question. Each
   question is independently retrieved; earlier answers are not sent as chat context.

Deep research uses the existing asynchronous LangGraph job API. The UI polls real
status and renders actual tools/evidence; it does not simulate streaming or claim
that stopping a browser wait cancels server work. Report downloads include the
returned source references, supporting quotes and any partial-coverage warning.
Generated Markdown images render as text so opening an answer cannot silently
fetch an external tracking URL.

## Uploads and ownership

Use Upload documents, drag/drop a PDF, or Browse files. The API supports one
text-based PDF per request, up to 20 MiB and 100 pages. Scans require OCR and are
rejected with an actionable message. Upload progress is indeterminate because
the API does not publish per-stage progress. A document becomes Ready only after
the real indexing response succeeds.

The library displays only confirmed API documents and known metadata: title or
filename, pages, PDF type, sample/private status. It does not invent file sizes,
upload dates or background queue counts. Initial loading, empty lists and errors
have separate states. A successful upload remains visible even if an older list
request finishes afterward. A confirmed private deletion also removes its scope
selection and associated tab history; included papers cannot be deleted.

Confirmed uploads and deletions run in the persistent library provider, so
changing routes does not interrupt their reconciliation. The library refreshes
on entry and after uncertain failures. An authorized operation may still finish
on the server if the entire browser tab closes.

## Persistence and supported features

Authentication is the existing anonymous HttpOnly browser-session cookie. There
are no account/password, OAuth, billing, logout or durable conversation APIs, so
this redesign does not show pretend controls for those features.

History and bookmarks contain actual responses/job references, capped at 32
most recent entries in React memory, including bookmarks. They survive client-side route changes and clear on a
refresh or tab close. Private questions, answers, source text and filenames are
never written to localStorage or sessionStorage. Only theme and sidebar
preferences use localStorage; they still work in memory when storage is blocked.
Browser-session uploads are server-owned and expire according to the existing
24-hour policy. Clearing tab history does not delete uploaded PDFs.

## File structure

```text
apps/web/
  app/
    page.tsx                 Public landing
    layout.tsx               Font, metadata, providers
    globals.css              Design tokens and shared controls/dialogs
    workspace/               Research workspace route
    research/[id]/           Existing job/report route, redesigned
    documents/ knowledge/    Document and knowledge views
    history/ saved/ settings/ about/
  components/
    app-providers.tsx        Public/API boundary and shared contexts
    app-shell.tsx            Collapsible/sidebar/mobile navigation and header
    public-chrome.tsx        Public navigation and footer
    brand.tsx                Native SVG product mark
    preferences.tsx          Theme/sidebar preferences only
    workspace-memory.tsx     Bounded, nonpersistent tab activity
    research-workspace.tsx   Composer, requests, source scope, current answer
    conversation-answer.tsx Answer and real actions
    conversation-list.tsx   History/bookmarks and search
    workspace-sources.tsx   Scope and returned evidence
    markdown-report.tsx     Safe Markdown and inline citation mapping
    citation-drawer.tsx     Exact quote verification/highlight and source details
    document-library.tsx    Real library, search/filter, details, confirmed deletion
    document-upload.tsx     Real upload/indexing interaction
    source-library.tsx      Ready-document state and stale-read protection
    settings-workspace.tsx  Functional appearance and privacy settings
    report-actions.tsx      Copy, bookmark, cited Markdown download
    modal-dialog.tsx        Native modal behavior and focus restoration
    backend-readiness.tsx   Existing API readiness/retry behavior
  lib/
    api.ts                   Typed, credentialed API requests and errors
    product.ts               Verified repository URL
  styles/
    marketing.css            Landing/About layouts
    workspace.css            Workspace/documents/history/settings
    research.css             Job/report/tool/evidence layouts
  tests/
    phase7.spec.ts            Preserved interaction/error/citation regressions
    redesign.spec.ts          New behavior, privacy and responsive coverage
    redesign-review.spec.ts   Privacy, mutation navigation, coverage and scope regressions
    request-rules.spec.ts     Existing scope rules
    proxy.spec.ts             Existing real Next proxy coverage
```

## Design and accessibility

Inter Variable and Lucide are bundled locally. Shared CSS variables define the
requested dark palette, light mode, surfaces, typography and spacing. The app uses
a 248px sidebar, a 68px collapsed state, a 64px header and a collapsible source pane.
On narrow screens, navigation and source inspection use native modal dialogs;
cards stack and controls remain reachable. There are skip links, visible keyboard
focus, labels, Escape handling, dialog focus restoration and reduced-motion rules.

No UI/animation framework or image-generation dependency was introduced. Motion
uses brief CSS transitions and truthful loading indicators.
