# Phase 7, step 1: Cold-start wake-up banner

On the initial app render, a shared readiness provider requests
`GET /api/v1/health`. It shows a wake-up message only if the request is still
pending after three seconds. The check has a 60-second deadline and distinguishes
ready, database-not-ready, unreachable, and timed-out states. Errors have a
retry action; the rest of the app can use the same readiness state to gate
service-dependent actions.

The existing service status panel reads the provider result, so it does not
issue another health request.

## Visual verification

1. Start the API and web app using the root README commands, then open the home
   page. Confirm the connection status resolves and the wake-up banner is absent.
2. Throttle or delay the health request for more than three seconds. Confirm the
   wake-up message appears and disappears after a successful response.
3. Block the health request. Confirm the error message offers a Retry action and
   does not leave an indefinite spinner.
4. Repeat at viewport widths of 360px, 768px, and 1280px. Confirm no horizontal
   overflow.

## Automated checks

From `apps/web`, run:

```powershell
npm run lint
npm run typecheck
npm run build
```

## Verification result

Mocked browser checks confirmed that an immediate ready response keeps the
banner hidden, a pending request shows the wake-up banner after three seconds,
and a 503 readiness response offers Retry and disables research actions. A
subsequent ready response clears the error and unlocks the workspace. Responsive
width results are recorded in [step 4](phase-7-step-4-live-timeline.md).

## Completion changes

Shared readiness now drives the shell connection pill and gates both question and
upload controls. The same-origin proxy permits the full 60-second wake-up budget
instead of cutting requests off after 30 seconds. Clock-controlled tests wait
for the actual request before checking3-second/60-second boundaries.
