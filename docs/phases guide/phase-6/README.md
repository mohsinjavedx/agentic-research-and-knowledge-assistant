# Phase 6 — Bounded agentic workflows

Phase 6 follows the implementation guide's five-step sequence:

1. [Typed graph state](phase-6-step-1-typed-state.md) — implemented and tested.
2. [Research graph topology](phase-6-step-2-graph-topology.md) — implemented and tested.
3. [Allowlisted read-only tools](phase-6-step-3-read-only-tools.md) — implemented and tested.
4. [Hard execution budgets](phase-6-step-4-execution-budgets.md) — implemented and tested.
5. [Asynchronous jobs and progress](phase-6-step-5-async-jobs.md) — implemented and tested.

The workflow must remain session-scoped, bounded to four iterations and six tool
calls, and use only read-only document tools. Each step records automated golden
set verification and a valid example for visual inspection in Swagger or the local
research job page.

Phase acceptance requires at least 85% of 25 multi-document tasks to produce
well-structured, cited reports; all runs must stay within the hard limits; and all
tool calls must pass argument and ownership validation. Passing unit/integration
tests alone does not establish the live task-completion rate.

## Status

All five implementation steps are implemented and tested. The graph and search
tool tests exercise all 40 Phase 3 golden queries, and PostgreSQL integration tests
cover the persisted job flow. The Phase 6 task-completion acceptance benchmark
remains pending because the available golden set does not include 25 multi-document
tasks.
