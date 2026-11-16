# Parser fixtures

Phase 1 will add malformed, scanned, encrypted, multi-column, table-heavy, and prompt-injection PDF fixtures. No parsing is performed by the Phase 0 API.

Steps 1-2 currently generate synthetic fixtures in memory through `apps/api/tests/unit/test_pdf_validation.py` and `apps/api/tests/conftest_layout.py`. They cover size/page boundaries, invalid/encrypted PDFs, columns, ruled tables, shaded code/text, blank pages, headers/footers, and an image-only page. These generated test inputs do not constitute the representative ten-paper acceptance corpus.

Step 3 adds rasterized text PDFs and mixed text/image documents in `apps/api/tests/unit/test_pdf_text_density.py`. These verify detection of image-only text, strict density thresholds, early termination, accepted mixed PDFs, and cleanup. Normal text fixtures were expanded to meet the default 50-character minimum.
