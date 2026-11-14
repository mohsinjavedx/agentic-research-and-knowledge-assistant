"use client";

import { useEffect, useState } from "react";
import { getHealth, type Health } from "@/lib/api";

type State = { kind: "loading" } | { kind: "error" } | { kind: "loaded"; health: Health };

export function ServiceStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = setTimeout(() => controller.abort(), 5000);
    getHealth(controller.signal).then(
      (health) => { if (active) setState({ kind: "loaded", health }); },
      () => { if (active) setState({ kind: "error" }); },
    ).finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [attempt]);

  const ready = state.kind === "loaded" && state.health.status === "ready";
  return (
    <section className="service-status" aria-label="Service status">
      <div className="status-heading" role="status" aria-live="polite">
        <span className={`status-dot ${ready ? "ready" : ""}`} aria-hidden="true" />
        <strong>{state.kind === "loading" ? "Checking the connection…" : ready ? "Services connected" : "Services need attention"}</strong>
      </div>
      {state.kind === "loaded" && <dl>
        <div><dt>Database</dt><dd>{state.health.db === "connected" ? "Connected" : "Unavailable"}</dd></div>
        <div><dt>Vector search</dt><dd>{state.health.pgvector ? `pgvector ${state.health.pgvector}` : "Unavailable"}</dd></div>
        <div><dt>Model settings</dt><dd>{state.health.model_configured ? "Configured" : "Incomplete"}</dd></div>
      </dl>}
      {state.kind === "error" && <p>The API could not be reached. Start the local API, then check again.</p>}
      {state.kind === "loaded" && !ready && <p>The API is running. Start PostgreSQL and apply the migrations to connect the workspace.</p>}
      <button className="text-button" type="button" disabled={state.kind === "loading"} onClick={() => { setState({ kind: "loading" }); setAttempt((value) => value + 1); }}>Check connection</button>
    </section>
  );
}
