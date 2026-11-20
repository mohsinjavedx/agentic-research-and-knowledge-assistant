# Phase 3, step 2: Session-scoped dense retrieval

The retrieval service embeds the query with the configured Phase 2 provider, then ranks chunks by PostgreSQL pgvector cosine distance. The SQL query always restricts results to the supplied `allowed_doc_ids` and uses deterministic chunk-ID ordering to break ties.

`POST /api/v1/search` requires the `session_id` cookie. When `document_ids` is omitted, the API resolves scope to ready global samples and ready, unexpired documents owned by the current session. Explicit document selections are checked against the same scope; missing and foreign-session IDs return the same 404. The route never trusts a caller-supplied ID as proof of ownership.

The response contains the retrieved chunk text, chunk/document IDs, one-based page number, and cosine similarity. `insufficient_evidence` is set when no evidence is found or the best similarity is at or below the configured threshold. Retrieval returns evidence only; answer generation and citation verification belong to Phase 4.

## Try the endpoint

Start the API and send a search request using a browser session cookie. Global sample papers are available to every session:

```powershell
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-WebRequest -Method Post -Uri 'http://127.0.0.1:8000/api/v1/session' -WebSession $session
$body = @{ query = 'How does the paper evaluate retrieval performance?' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/search' -WebSession $session -ContentType 'application/json' -Body $body
```

The route is also documented in the API's `/docs` interface.

## Source files

| File | Purpose |
| --- | --- |
| [search.py](../../../apps/api/app/api/v1/search.py) | Session/document authorization and HTTP response contract. |
| [dense.py](../../../apps/api/app/services/retrieval/dense.py) | Query embedding and scoped cosine-distance ranking. |
| [retrieval.py](../../../apps/api/app/schemas/retrieval.py) | Validated request and result schemas. |
| [test_retrieval.py](../../../apps/api/tests/integration/test_retrieval.py) | PostgreSQL-backed result-scope and foreign-session checks. |

