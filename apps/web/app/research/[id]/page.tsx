"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getResearchJob, type ResearchJob } from "@/lib/api";

type PageState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "loaded"; job: ResearchJob };

export default function ResearchJobPage() {
  const { id } = useParams<{ id: string }>();
  const [state, setState] = useState<PageState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const job = await getResearchJob(id, controller.signal);
        if (!active) return;
        setState({ kind: "loaded", job });
        if (job.status === "queued" || job.status === "running") {
          timer = setTimeout(() => void poll(), 1500);
        }
      } catch {
        if (active && !controller.signal.aborted) setState({ kind: "error" });
      }
    }

    void poll();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [id]);

  if (state.kind === "loading") {
    return <section className="document-page"><p role="status">Loading research job…</p></section>;
  }
  if (state.kind === "error") {
    return <section className="document-page"><p className="section-label">Research job</p><h1>Job unavailable.</h1><p role="alert">Check the job ID and confirm that this browser session owns it.</p></section>;
  }

  const { job } = state;
  return (
    <section className="document-page research-job">
      <p className="section-label">Research job</p>
      <h1>{job.report?.title ?? "Research in progress"}</h1>
      <p className="research-query">{job.query}</p>
      <div className={`research-status ${job.status}`} role="status" aria-live="polite">
        <strong>{job.status}</strong>
        <span>{job.iterations} of 4 rounds · {job.tool_calls_count} of 6 tool calls</span>
      </div>

      <section className="research-progress" aria-labelledby="progress-heading">
        <h2 id="progress-heading">Progress</h2>
        {job.steps.length === 0 ? <p>Waiting for the first workflow step.</p> : (
          <ol>
            {job.steps.map((step, index) => (
              <li key={`${step.name}-${index}`}>
                <strong>{step.name.replaceAll("_", " ")}</strong>
                <span>{step.message}</span>
                <small>Round {step.iteration} · {step.tool_calls_count} tool calls</small>
              </li>
            ))}
          </ol>
        )}
      </section>

      {job.error_code && <p className="research-error" role="alert">Workflow stopped: {job.error_code}</p>}

      {job.report && (
        <article className="research-report">
          <h2>Findings</h2>
          {job.report.partial_coverage && <p className="research-disclaimer">{job.report.disclaimer}</p>}
          <p>{job.report.summary}</p>
          {job.report.sections.map((section, index) => (
            <section key={`${section.heading}-${index}`}>
              <h3>{section.heading}</h3>
              <p>{section.content}</p>
            </section>
          ))}
          <h2>Verified citations</h2>
          {job.report.citations.length === 0 ? <p>No claims passed citation verification.</p> : (
            <ol>
              {job.report.citations.map((citation) => (
                <li key={`${citation.chunk_id}-${citation.quote_start}-${citation.quote_end}`}>
                  <p>{citation.claim}</p>
                  <blockquote>{citation.quote}</blockquote>
                  <small>Page {citation.page_number} · document {citation.document_id}</small>
                </li>
              ))}
            </ol>
          )}
        </article>
      )}
    </section>
  );
}
