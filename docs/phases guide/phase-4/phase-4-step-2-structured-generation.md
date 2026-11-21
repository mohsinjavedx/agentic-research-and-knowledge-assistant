# Phase 4, step 2: Structured answer generation

Both providers validate Pydantic `GroundedResponse` output. Local generation uses Ollama's native `/api/chat` endpoint with the response JSON schema in `format`. Hosted generation uses `instructor` and an OpenAI-compatible chat client configured through `HOSTED_LLM_BASE_URL`, `HOSTED_LLM_MODEL`, and the server-side `HOSTED_LLM_API_KEY`. Credentials are sent only as the provider authorization header and are never included in the prompt or API response.

`POST /api/v1/answer` accepts the same query and optional document selection as search, with `top_k` limited to 1–10. It requires the session cookie and uses the same visibility resolver as `POST /api/v1/search`. The response contains an answer, checked citations, abstention and degraded-mode flags, all retrieved `evidence`, and the exact `used_evidence` excerpts supplied to completed generation.

Configuration examples:

```dotenv
LLM_PROVIDER=local
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_NUM_CTX=2048
LLM_MAX_OUTPUT_TOKENS=512
LLM_TIMEOUT_SECONDS=90
```

```dotenv
LLM_PROVIDER=hosted
HOSTED_LLM_BASE_URL=https://api.groq.com/openai/v1
HOSTED_LLM_MODEL=your-configured-model
HOSTED_LLM_API_KEY=configure-this-locally
```

Hosted inference sends the retrieved evidence to the selected provider. Use only a provider and data-handling path approved for the documents being queried. Production hosted endpoints require HTTPS.

## Local context and citation limits

`OLLAMA_NUM_CTX` is sent as native `options.num_ctx`, and `LLM_MAX_OUTPUT_TOKENS` as `options.num_predict` for local generation. The previous `/v1` adapter sent `options.num_ctx` through an unsupported compatibility parameter, so the configured context was not applied. See [Ollama's compatibility documentation](https://docs.ollama.com/api/openai-compatibility) and [native chat API](https://docs.ollama.com/api/chat).

For the local provider, startup validation requires `LLM_MAX_OUTPUT_TOKENS < OLLAMA_NUM_CTX`. This basic check prevents an impossible output reservation; the per-request budget still checks whether the actual question and source passages fit.

The providers select focused, complete Markdown passages from retrieved chunks. Local packing retains passages that fit an estimated input budget after reserving output tokens, schema overhead, 25% tokenizer margin, and chat-template overhead. It may skip a passage that cannot fit and continue to later ones; lists and tables are not clipped. The estimate uses `cl100k_base`, not the model's own tokenizer, and is not an exact context guarantee. A request fails safely if no complete passage fits. Larger contexts cost inference time and memory.

Model context indices are mapped explicitly back to original retrieval indices and source ranges. The request-specific JSON schema permits only supplied context indices. Citation quotes must occur inside the supplied passage, claims must occur in the answer, and all non-whitespace answer characters must be covered. These are provenance/coverage checks, not semantic entailment. A token-limit-truncated response or malformed JSON is rejected. Local inference has one asynchronous request with a total deadline and no automatic retry. See the [quality improvement guides](quality-improvements/README.md).

## Verification

From `apps/api`:

```powershell
uv run pytest -q tests/unit/test_ollama_provider.py tests/unit/test_answer_api.py tests/unit/test_generation.py tests/unit/test_config.py
```

These tests exercise the HTTP contract with a fake provider and native Ollama requests with a mock HTTP transport. They do not establish general model answer quality. On 21 November 2026, the exact five-benchmark query from the reported failure was also verified against the running API and local `llama3.2:3b`: it returned the correct five names and a page 7 citation in 14.4 seconds with `degraded_mode: false`. See the [evaluation report](../../evaluation-report.md) for the diagnostic details and remaining full-phase acceptance work.

## Source

- [llm.py](../../../apps/api/app/providers/llm.py) — native Ollama adapter, hosted Instructor adapter, and provider selection.
- [answers.py](../../../apps/api/app/schemas/answers.py) — strict generation and HTTP response schemas.
- [answers.py](../../../apps/api/app/api/v1/answers.py) — session-scoped answer endpoint.
