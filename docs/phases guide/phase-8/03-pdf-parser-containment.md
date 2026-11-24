# Step 3: bounded PDF parsing

The parent stages at most 20 MiB under a private `research-pdf-*` system temporary
directory, using a UUID filename. It rejects traversal, MIME/extension/signature
mismatches and oversized bytes before native parsing. It owns cleanup on every exit.

`PDFValidator` now checks untrusted pypdf structure in a spawned worker. The default
`PDFIngestionService`, browser embedding path and extraction/preparation CLI use
`SandboxedPDFExtractor` for native PyMuPDF/Markdown work in another spawned worker.
The child receives only the staged path and bounded parser settings; embedding
models stay in the parent. Normalization, page mappings and chunk algorithms remain
the established implementations. Native adapter tests may explicitly inject the
raw extractor to test dependency faults; production entry points use containment.

The parent attaches a Windows Job Object before authorizing parsing: one active
process, 768 MiB process memory, kill on job close. Linux workers apply a 768 MiB
address-space ceiling, disable core dumps and limit file descriptors. If limits
cannot be installed, parsing fails closed. Replies are bounded JSON bytes (8 MiB),
never child-controlled pickle. Page text is bounded to 1 million characters, total
text to 2 million. Incoming diagnostic messages are reconstructed from safe codes.

Structure checking and each extraction stage/page have a maximum 15-second deadline.
Progress must be strictly sequential and cannot exceed the configured page/stage
count, so heartbeat spam cannot keep a job alive indefinitely. Document-wide density,
background-fill and header scans each have the same 15-second ceiling; this can
reject a complicated valid PDF sooner than a per-page-only policy. An IPC receiver
thread keeps a partial frame from blocking the watchdog. On failure the parent
terminates, escalates to kill if needed, joins the child and removes staged files.
Timeouts produce a safe 422 `PDF_PARSER_TIMEOUT`; parser crashes return a safe 422.
Existing validation codes and OCR rejection are preserved.

Cancelling an active upload sets a parent-side cancellation event. The supervisor
checks it at most every 50 ms, kills/joins its child and unwinds the staging context.
The HTTP task waits for worker/source cleanup before returning cancellation, even
if cancellation is repeated. Phase boundaries check cancellation before starting
normalization, chunking or embedding, so an abandoned parsing job does not proceed
to inference. Already-running trusted embedding work finishes before its source
closes; it cannot be killed as a thread. Queued cancellation still closes its
stream immediately. A regression test observes a real active child and staged
file, cancels the request, and verifies both are gone when cancellation returns.

From `apps/api`:

```powershell
uv run pytest tests/unit/test_pdf_sandbox.py tests/unit/test_pdf_validation.py tests/unit/test_pdf_extraction.py tests/unit/test_pdf_validation_cli.py -q
```

Tests cover hangs, crashes, oversized/malformed IPC, duplicate progress, real text
extraction, invalid signatures/structure, traversal, oversize uploads and temporary
cleanup. The first run passed 77 cases; one CLI fault-injection fixture needed to
target the new supervised adapter instead of monkeypatching a different process.
Final results are in the verification guide.

This is process/resource containment, not a virtual machine or filesystem/network
isolation boundary against arbitrary native-code execution. Run the API as a
non-root service (the existing Docker image does) and keep parsers patched.
