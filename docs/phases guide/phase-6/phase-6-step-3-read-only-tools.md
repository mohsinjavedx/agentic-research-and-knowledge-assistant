# Phase 6, step 3: Allowlisted read-only tools

The research tool registry exposes exactly three operations:

- `search_documents(query, doc_ids, top_k)` — shared dense/hybrid retrieval over
  selected in-scope documents, capped at ten hits.
- `get_document_outline(doc_id)` — extracts Markdown headings from indexed chunks;
  when headings are absent, it returns page-level entries.
- `compare_sections(doc_a_id, doc_b_id, topic)` — separately retrieves up to three
  passages from each of two distinct documents.

Each tool has a strict Pydantic argument schema that rejects unknown fields,
duplicate IDs, invalid limits, and blank queries. The registry rejects every tool
name except the three above. Before a read, the service checks the requested IDs
against the graph's initial allowlist and resolves current session visibility again.
Retrieval SQL receives only the validated selected IDs; the outline SQL repeats the
document scope and ready-status conditions. These operations do not mutate documents.

## Golden-data verification

From `apps/api`:

```powershell
uv run pytest -q tests/unit/test_research_tools.py
$env:RUN_DB_TESTS = "1"
uv run pytest -q tests/integration/test_research_tools.py
```

The unit suite validates all 40 fixed Phase 3 questions through `search_documents`
with deterministic retrieval, plus rejection of arbitrary tools, malformed
arguments, duplicate comparison documents, and out-of-scope IDs. The PostgreSQL
integration test creates sample, current-session, and foreign-session documents and
verifies actual outline, search, comparison, and ownership behavior.

## Visual example

Inspect the sample outline in the PostgreSQL integration test in the VS Code Testing
view. A document without Markdown headings returns a structured result like:

```json
{
  "filename": "research-sample.pdf",
  "sections": [
    {"heading": "Page 1", "page_number": 1, "chunk_index": 0},
    {"heading": "Page 2", "page_number": 2, "chunk_index": 1}
  ]
}
```

For a document with headings, `sections` contains those heading titles and their
original page/chunk locations instead. Step 5 exposes these tool results through
the persisted research job so the same output can be inspected in Swagger.

## Source

- `apps/api/app/services/research/tools.py` — implementation and allowlisted dispatch.
- `apps/api/app/schemas/research.py` — validated arguments and output models.
- `apps/api/tests/unit/test_research_tools.py` and
  `apps/api/tests/integration/test_research_tools.py` — golden, validation, and
  PostgreSQL scope tests.
