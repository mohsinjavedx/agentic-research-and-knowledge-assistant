# Step 4: structured, privacy-safe telemetry

Every completed HTTP request records `request_id`, hashed `session_id`, route
template, status, `latency_ms`, `tokens_used`, `provider` and `error_code`. Missing
or invalid sessions produce null session identity; raw cookies/IPs are excluded.
Unknown routes are logged as `unmatched`. Quota refusals before routing use only
the known protected endpoint constant. Query strings, filenames, PDFs, prompts,
answers, raw provider exceptions and credentials are never telemetry fields.

`RequestTelemetry` uses a ContextVar with a shared, locked accounting object.
`asyncio.to_thread` carries the context, and the upload executor now explicitly
copies it too. This preserves request correlation and usage through worker threads.
Each real model/batch call starts an accounting entry before work begins:

- Hosted generation reads SDK `completion.usage.total_tokens` through Instructor's
  `create_with_completion`; failed calls count actual completion usage only when
  every attempt reports it. Instructor's initialized zero accumulator is never
  treated as a provider-reported count after a timeout/unknown response.
- Ollama reads `prompt_eval_count + eval_count` when supplied.
- Hosted embeddings read reported `usage.total_tokens` when supplied.
- Local ONNX embeddings count actual non-padding input tokens from their masks.
- Optional TinyBERT reranking also counts actual non-padding pair tokens per batch.
- No model call means zero. Any unknown/pending call makes the total null, rather
  than substituting an estimate or claiming zero cost. A mixed request may have
  `provider: "hosted,local"`.

`latency_ms` ends when the final response body is sent. `background_ms` records
work after the response, and `total_ms` includes it. Research BackgroundTasks can
therefore finish accounting without making a fast submission look like a slow
HTTP response. Unexpected background failures are sanitized after the response;
they do not print raw tracebacks containing private inputs.

The JSON formatter allows only known fields. Third-party Instructor/OpenAI/httpx/
httpcore/pypdf logging is suppressed because their exception logging can echo
provider error bodies, source text or request headers. Fixed application events
and stable error codes remain available. Start Uvicorn with `--no-access-log` so
its separate request log cannot expose query strings.

From `apps/api`:

```powershell
uv run pytest tests/unit/test_telemetry.py tests/unit/test_health.py tests/unit/test_llm_provider.py tests/unit/test_ollama_provider.py tests/unit/test_embeddings.py -q
```

Observed: 51 focused telemetry/provider/health/CLI tests passed; full initial
regression run passed 397 tests. Telemetry assertions cover hashing, route
redaction, actual/unknown usage, copied thread context, separate background timing
and dependency-log suppression. Final checks and live observations are recorded
in [verification](verification.md).
