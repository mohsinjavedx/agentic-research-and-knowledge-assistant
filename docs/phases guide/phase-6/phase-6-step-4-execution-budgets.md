# Phase 6, step 4: Hard execution budgets

The graph accepts a positive per-node LLM timeout and limits that cannot exceed the
Phase 6 hard caps: four execution rounds and six tool calls. Each LLM-capable graph
node (`plan`, `assess_sufficiency`, `synthesize`, and citation verification) runs
under its own timeout. A timeout raises the safe error code
`RESEARCH_NODE_TIMEOUT` and identifies the static node name for job diagnostics.

The allowlisted tool registry reserves a call slot before dispatch, using an async
lock so concurrent requests cannot pass the six-call limit together. Invalid
arguments and unknown tool names are rejected before reserving a slot. The graph
also passes the executor the remaining call allowance and rejects results that
claim more calls than the remaining budget.

When evidence remains insufficient at either hard cap, the graph stops retrieving,
synthesizes with `partial_coverage: true`, and includes a disclaimer. These controls
do not make model output reliable by themselves; the report still needs citation
verification.

## Verification

From `apps/api`:

```powershell
uv run pytest -q tests/unit/test_research_graph.py tests/unit/test_research_tools.py
```

Tests check four-round and six-call stopping, concurrent registry calls, and
timeouts on each LLM-capable node. A timed-out node raises a typed error instead of
silently returning an empty report.

## Visual example

Run the graph suite in the VS Code Testing view and open
`test_graph_stops_adding_tools_at_tool_call_limit`. Its valid insufficient-evidence
example ends with:

```json
{
  "iterations": 3,
  "tool_calls_count": 6,
  "final_report": {
    "partial_coverage": true,
    "disclaimer": "The workflow reached its execution budget; this report may have partial coverage."
  }
}
```

The completed job API in step 5 will expose these same fields in `GET
/api/v1/research/{job_id}`.

## Source

- `apps/api/app/services/research/graph.py` — node timeouts, max rounds, and bounded routing.
- `apps/api/app/services/research/tools.py` — concurrency-safe tool call counter.
- `apps/api/tests/unit/test_research_graph.py` and
  `apps/api/tests/unit/test_research_tools.py` — cap and timeout coverage.
