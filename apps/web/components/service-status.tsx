"use client";

import { useBackendReadiness } from "@/components/backend-readiness";

export function ServiceStatus() {
  const { readiness, retry } = useBackendReadiness();
  const ready = readiness.kind === "ready";
  return (
    <section className="service-status" aria-label="Service status">
      <div className="status-heading" role="status" aria-live="polite">
        <span className={`status-dot ${ready ? "ready" : ""}`} aria-hidden="true" />
        <strong>
          {readiness.kind === "checking"
            ? "Checking the connection…"
            : ready
              ? "Services connected"
              : "Services need attention"}
        </strong>
      </div>
      {(readiness.kind === "ready" || readiness.kind === "not_ready") && (
        <dl>
          <div>
            <dt>Database</dt>
            <dd>{readiness.health.db === "connected" ? "Connected" : "Unavailable"}</dd>
          </div>
          <div>
            <dt>Vector search</dt>
            <dd>
              {readiness.health.pgvector ? `pgvector ${readiness.health.pgvector}` : "Unavailable"}
            </dd>
          </div>
          <div>
            <dt>Model settings</dt>
            <dd>{readiness.health.model_configured ? "Configured" : "Incomplete"}</dd>
          </div>
        </dl>
      )}
      {readiness.kind === "not_ready" && (
        <p>
          The API is running. Start PostgreSQL and apply the migrations to connect the workspace.
        </p>
      )}
      {readiness.kind === "unavailable" && (
        <p>The API could not be reached. Check the server, then retry.</p>
      )}
      {readiness.kind === "timed_out" && (
        <p>The connection check timed out. Retry when the server is available.</p>
      )}
      <button
        className="text-button"
        type="button"
        disabled={readiness.kind === "checking"}
        onClick={retry}
      >
        Check connection
      </button>
    </section>
  );
}
