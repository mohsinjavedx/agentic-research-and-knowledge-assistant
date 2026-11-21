# Phase 4, step 1: Prompt isolation

Retrieved text is untrusted input. The answer prompt keeps system instructions separate from the user question and wraps each retrieved chunk in an `<evidence>` element containing its UUID, document UUID, and one-based page number. XML metacharacters in both the question and evidence are escaped before serialization. The system prompt directs the model to treat evidence as quoted data, ignore instructions inside it, avoid hidden prompts or secrets, and cite only supplied evidence.

## Verification

From `apps/api`:

```powershell
uv run pytest -q tests/unit/test_generation.py
```

The prompt test injects instruction-like text and checks that it remains escaped inside evidence rather than becoming a system or XML element. This verifies prompt construction, not a model's behavior; run the live injection scenario after configuring a model as part of step 4.

## Source

- [prompt.py](../../../apps/api/app/services/generation/prompt.py) — system instructions and escaped message construction.
- [test_generation.py](../../../apps/api/tests/unit/test_generation.py) — prompt isolation and injection-string coverage.
