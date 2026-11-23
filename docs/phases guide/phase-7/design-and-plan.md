# Phase 7 completion — 23 November 2026

User request: complete the existing Phase 7 work with a modern, dynamic, elegant UI and effects. Source: implementation guide v2.0, page 13. Preserve the dirty phase-7 branch, including the user's Phase 6 progress-snapshot changes; leave all work uncommitted.

## Design

Use the existing Next16/React19 application and API. Keep Research desk as the product name. Choose a focused research desk over a separate marketing landing page: a persistent navigation rail, central question composer/answer, and visible selected papers. A decorative dark dashboard would give less space to reading and sources.

Palette: canvas #f4f7f8, surface #ffffff, ink #182f38, muted #61717a, teal #087e79, line #dfe8eb. Use locally bundled Manrope for interface and display text; no runtime font requests. Controls have10px radii, panels18px, status pills rounded. Motion responds to mode selection, answer arrival, source drawer opening, and real workflow progress; reduced-motion users get immediate state changes. No fake metrics or running activity.

```text
navigation | title / service connection
           | question composer             | selected papers
           | one-click starter questions   | add PDF / library
           | answer + inline source badges | source guidance
```

Retain three preselected samples, three real starter questions, two-second job polling, safe Markdown, and current API citation verification. Make the native modal drawer keyboard-contained, highlight Unicode code-point quote ranges correctly, and preserve original source text. Bound requests and job waiting, and show retryable errors rather than endless loading.

Complete the missing upload/error acceptance path with a minimal session-scoped PDF upload/list API that reuses the existing parser/embedding/indexing service. Stream at most 20 MiB, keep100-page validation, reject OCR through its existing typed error, clean temporary files, and expose only current-session documents plus samples. No arbitrary file paths, new parser, OCR engine, or Phase 8 rate-limit system. Use same-origin API rewrites by default so anonymous cookies work with localhost and 127.0.0.1.

## Implementation plan

1. Write browser regressions for first-visit answer→Unicode citation→multi-paper timeline, modal keyboard behavior, sleeping/unavailable health,429/OCR errors, request timeout, and zero horizontal overflow at 360/768/1280. Observe failures. Add Playwright and one icon family; preserve existing packages.
2. Add API upload/list tests before implementation. Reuse the existing pipeline with a stream entry point; implement session visibility and safe error contracts. Run targeted API tests and then the full suite.
3. Build the shared navigation/connection shell, composer/source library, inline citation rendering and native drawer. Add locally bundled font, coherent CSS, loading/error/empty states, and reduced-motion effects. Verify each flow with Playwright.
4. Finish the research run page with actual plan/tool/evidence/report sections and bounded polling/retry. Verify running→completed and error/timeout behavior.
5. Run lint, TypeScript, production build, all browser tests, API tests and formatting/types. Inspect desktop/mobile screenshots. Update the four step guides, acceptance evidence, and runGuide.txt. Request one read-only final review if the review service is available; disclose any unavailable check.

## Review focus

- User-owned Phase 6 and Phase 7 edits remain intact; no resets, commits or unrelated phase work.
- Native modal focus isolation, Escape/return focus, Unicode source ranges, and no invented highlights.
- Cookie/session consistency, ownership, unexpired upload visibility, bounded PDF streams and cleanup.
- No overlapping polls, unmount leaks, indefinite waiting, or stale answers after source changes.
- Real browser checks at 360/768/1280, reduced motion, malicious Markdown and clear actionable errors.

## Progress

All implementation steps delivered and one fresh senior review completed. The original first-visit/inline-citation/upload tests failed before implementation. Review regressions reproduced the 10 MB/30-second proxy failures, lost inline focus and missing private filenames; all were fixed. Native parser serialization/cancel cleanup tests pass. A delayed library read was also observed discarding a newer upload; the library now merges mutations made during the request. Final full API/database suite:375 passed. Frontend suite:16 passed, including all target widths; real proxy suite:2 passed. Final production/static checks and screenshot inspection are recorded in verification.md. No live-model quality gate is inferred from fixtures.
