# Groq hosted generation

Generation was switched to Groq on 21 November 2026 at the user's request. The root `.env` now selects:

```dotenv
LLM_PROVIDER=hosted
HOSTED_LLM_BASE_URL=https://api.groq.com/openai/v1
HOSTED_LLM_MODEL=openai/gpt-oss-120b
HOSTED_LLM_API_KEY=configure-this-locally
```

The existing configured key was preserved, verified with Groq's models endpoint, and confirmed to have access to `openai/gpt-oss-120b`. No key value is included in documentation or saved reports. `.env` remains ignored by Git. `.env.example` now reflects this provider/model with an empty key field.

The existing hosted adapter uses an OpenAI-compatible client and Instructor/Pydantic schema validation. No application-code change was required. The backend was reloaded and `/api/v1/health` confirmed `llm_provider: hosted` with the database connected. Embeddings and PostgreSQL remain local. Hosted inference sends selected source excerpts to Groq; local `OLLAMA_NUM_CTX` limits do not apply to the hosted path, which supplies all focused passages.

## Live verification

The original benchmark question, restricted to document `35d86749-bf13-55ac-8008-231937b43bab` with `top_k: 5`, returned HTTP200 in **3.15 seconds**, including approximately **1.68 seconds** generation. It named all five benchmarks, returned a page7 source quote and citation, and had `insufficient_evidence: false` and `degraded_mode: false`. Five focused excerpts were supplied to generation. The source quote and its offsets were verified against the full retrieved chunk.

Four additional pilot requests returned HTTP200:

- E-EVAL question count: **4,351**, with a checked source quote, in **1.39 seconds**.
- GPT-4o OpenBookQA accuracy with RAG/code interpreter: **93.2%**, with a checked source quote, in **1.54 seconds**.
- OpenBookQA/TQA comparison: abstained, in **1.13 seconds**; this case remains unresolved.
- Out-of-corpus question: correctly abstained before generation, in **0.12 seconds**.

The factual values match the independently audited source answers. These are five pilot cases, not a replacement for the full40-question quality evaluation or the30-answer human audit. Different local/hosted context packing also prevents interpreting the results as an isolated model-only comparison. No claim is made that all retrieval, synthesis, or semantic citation-support issues are solved.

Preserved reports:

- `data/eval/groq-gpt-oss-120b-benchmark-smoke-2026-11-21.json`
- `data/eval/groq-gpt-oss-120b-pilot-2026-11-21.json`

For broader evaluation, run the existing evaluator to a fresh file. It refuses to overwrite earlier reports:

```powershell
uv run --project apps/api python scripts/run_grounded_qa_eval.py --output data/eval/new-groq-review.json
```

Provider references: [model details](https://console.groq.com/docs/model/openai/gpt-oss-120b), [structured outputs](https://console.groq.com/docs/structured-outputs).
