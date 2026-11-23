# Phase 7, step 3: Interactive citation drawer

Answer and report citations render as source badges. Activating a badge opens a
reusable drawer with the source document, page, cosine similarity, citation
claim, and original evidence chunk. The quoted span is highlighted only when
the citation's character offsets match the exact quote in that chunk. A badge
is disabled when its source evidence was not returned.

## Visual verification

1. Ask a starter question or open a completed research report.
2. Activate a **[Doc N, p. N]** citation badge.
3. Confirm the drawer shows the matching document and page, the similarity
   score, claim, and complete source passage with the exact quote highlighted.
4. Close with the button, backdrop, or Escape; focus returns to the citation
   badge.

The browser acceptance check used a clearly mocked response and confirmed the
page-7 passage, similarity `0.912`, and exact quote highlighting. It does not
substitute for a live-model citation-quality evaluation; Phase 4's verifier
continues to enforce quote-to-chunk offsets on the API side.

## Completion changes

Inline badges follow exact Markdown claim matches; formatted claims remain in the
verified source list. The native modal traps Tab/Shift+Tab, closes with Escape,
backdrop or close button, and restores focus to the original badge. Stable
Markdown renderer identities prevent trigger remounts. Private filenames are
resolved from the library; copy status resets for each citation.

The source is the original normalized chunk returned by the API, with one-based
page and cosine relevance score. Offsets count Unicode code points, so an emoji
before a quote does not shift the highlight. Mismatched ranges show the entire
source with an explicit unavailable note. This is a source-text inspector rather
than a PDF coordinate viewer. Motion respects reduced-motion preferences.
