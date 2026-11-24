"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import {
  ArrowLeft,
  RefreshCw as ArrowsClockwise,
  Check,
  CircleCheck as CheckCircle,
  BrainCircuit as Compass,
  BrainCircuit as Sparkle,
  CircleAlert as WarningCircle,
} from "lucide-react";
import { CitationBadge, CitationDrawer } from "@/components/citation-drawer";
import { useBackendReadiness } from "@/components/backend-readiness";
import MarkdownReport from "@/components/markdown-report";
import { type ResearchCitation } from "@/lib/api";
import { sampleDocumentLabel } from "@/lib/samples";
import { useResearchJob } from "@/lib/use-research-job";
import { useSourceLibrary } from "@/components/source-library";
import { ReportActions } from "@/components/report-actions";

export default function ResearchJobPage() {
  const { id } = useParams<{ id: string }>();
  const { isReady, readiness, retry: retryHealth } = useBackendReadiness();
  const { state, retry } = useResearchJob(id, isReady);
  const { documents } = useSourceLibrary();
  const [selectedCitation, setSelectedCitation] = useState<ResearchCitation | null>(null);
  const citationTrigger = useRef<HTMLButtonElement | null>(null);
  const closeCitation = useCallback(() => setSelectedCitation(null), []);
  const backLink = (
    <Link className="back-link" href="/research">
      <ArrowLeft size={15} />
      Back to research
    </Link>
  );
  if (state.kind === "loading")
    return (
      <section className="research-job page-enter">
        {backLink}
        <span className="context-label">
          <Compass size={16} />
          Deep research
        </span>
        <h1>{isReady ? "Opening your research." : "Connecting to your research."}</h1>
        <div className="run-loading" role="status">
          <div className="loading-label">
            <span className="activity-indicator" />
            {isReady ? "Loading the latest progress" : "Waiting for the research service"}
          </div>
          <div className="skeleton-line" />
          <div className="skeleton-line short" />
          {!isReady && readiness.kind !== "checking" && (
            <button className="text-button" onClick={retryHealth}>
              Retry connection
            </button>
          )}
        </div>
      </section>
    );
  if (state.kind === "error")
    return (
      <section className="research-job page-enter">
        {backLink}
        <h1>Let&apos;s reconnect.</h1>
        <div className="notice error" role="alert">
          <strong>Run status is unavailable.</strong>
          <p>{state.message}</p>
        </div>
        <button className="button secondary" onClick={retry}>
          <ArrowsClockwise size={17} />
          Retry job status
        </button>
      </section>
    );
  const { job } = state;
  const complete = job.status === "completed";
  const ongoing = job.status === "queued" || job.status === "running";
  const reportMarkdown = job.report
    ? [
        job.report.summary,
        ...job.report.sections.map((section) => `## ${section.heading}\n\n${section.content}`),
      ].join("\n\n")
    : "";
  const coverageWarning = job.report?.partial_coverage
    ? (job.report.disclaimer ??
      "This report has partial source coverage. Inspect the available evidence before relying on its conclusions.")
    : null;
  function openCitation(citation: ResearchCitation, trigger: HTMLButtonElement) {
    citationTrigger.current = trigger;
    setSelectedCitation(citation);
  }
  return (
    <section className="research-job page-enter">
      {backLink}
      <header>
        <span className="context-label">
          <Compass size={16} />A few papers. A wider perspective.
        </span>
        <h1>{job.report?.title ?? "Following the evidence."}</h1>
        <p className="research-query">{job.query}</p>
      </header>
      <div className={`research-status ${job.status}`} role="status" aria-live="polite">
        <strong>
          {complete ? (
            <CheckCircle size={17} />
          ) : job.status === "failed" ? (
            <WarningCircle size={17} />
          ) : (
            <span className="activity-indicator" />
          )}
          {job.status === "completed"
            ? "Research complete"
            : job.status === "running"
              ? "Research in progress"
              : job.status === "queued"
                ? "Waiting to begin"
                : "Research stopped"}
        </strong>
        <span>
          {job.iterations} of 4 rounds, {job.tool_calls_count} of 6 tool calls
        </span>
      </div>
      {job.error_code && (
        <div className="notice error" role="alert">
          <strong>This run could not finish.</strong>
          <p>
            {job.error_code === "LLM_RATE_LIMITED"
              ? "The model request limit was reached. Wait a few minutes, then start a new comparison."
              : "The service stopped this run. Your collected evidence remains below. Try a more focused comparison."}
          </p>
        </div>
      )}
      <div className="research-run-grid">
        <article className="run-report" aria-labelledby="report-heading">
          <div className="section-heading">
            <h2 id="report-heading">{job.report ? "Final report" : "Your research report"}</h2>
            <Sparkle size={20} color="var(--accent)" />
          </div>
          {job.report ? (
            <div className="research-report reveal-in">
              {coverageWarning && <p className="research-disclaimer">{coverageWarning}</p>}
              <MarkdownReport
                content={reportMarkdown}
                citations={job.report.citations}
                evidence={job.evidence}
                onCitationOpen={openCitation}
              />
              <ReportActions
                jobId={job.job_id}
                query={job.query}
                title={job.report.title}
                content={reportMarkdown}
                documentIds={[...new Set(job.evidence.map((item) => item.document_id))]}
                coverageWarning={coverageWarning}
                citations={job.report.citations}
              />
              <section className="report-citations">
                <h3>Verified source passages</h3>
                {job.report.citations.length ? (
                  <div className="report-citation-list">
                    {job.report.citations.map((citation, index) => (
                      <CitationBadge
                        key={`${citation.chunk_id}-${index}`}
                        citation={citation}
                        disabled={
                          !job.evidence.some(
                            (item) =>
                              item.chunk_id === citation.chunk_id &&
                              item.document_id === citation.document_id,
                          )
                        }
                        onOpen={openCitation}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="empty-message">No claims passed citation verification.</p>
                )}
              </section>
            </div>
          ) : (
            <div className="run-waiting">
              {ongoing ? (
                <>
                  <span>
                    <span className="activity-indicator" />A thoughtful answer takes a little
                    digging.
                  </span>
                  <p>
                    The plan, tool calls, and collected passages appear as the research progresses.
                    Your cited report will arrive here.
                  </p>
                  <div className="skeleton-line" />
                  <div className="skeleton-line" />
                  <div className="skeleton-line short" />
                </>
              ) : (
                <p>
                  No final report is available for this run. Inspect any collected evidence or try a
                  new comparison.
                </p>
              )}
            </div>
          )}
        </article>
        <aside className="run-activity">
          <section aria-labelledby="progress-heading">
            <h2 id="progress-heading">Agent plan and progress</h2>
            {job.steps.length ? (
              <ol className="research-timeline">
                {job.steps.map((step, index) => (
                  <li key={`${step.name}-${index}`}>
                    <span className={`timeline-dot ${step.status}`}>
                      {step.status === "completed" && <Check size={10} strokeWidth={3} />}
                    </span>
                    <div className="timeline-step-heading">
                      <strong>{step.name.replaceAll("_", " ")}</strong>
                      <span className={`step-state ${step.status}`}>{step.status}</span>
                    </div>
                    <p>{step.message}</p>
                    <small>
                      Round {step.iteration} &middot; {step.tool_calls_count} tool calls
                    </small>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-message">The plan appears when the first step completes.</p>
            )}
          </section>
          <section className="research-tools" aria-labelledby="tools-heading">
            <h2 id="tools-heading">Tool calls</h2>
            {job.tool_calls.length ? (
              <ol className="tool-list">
                {job.tool_calls.map((call, index) => (
                  <li key={`${call.name}-${index}`}>
                    <div className="timeline-step-heading">
                      <strong>{call.name.replaceAll("_", " ")}</strong>
                      <span className={`step-state ${call.status}`}>{call.status}</span>
                    </div>
                    <p>{call.result_summary ?? "The tool has not returned a result yet."}</p>
                    <details>
                      <summary>Inspect call</summary>
                      <pre>{JSON.stringify(call.arguments, null, 2)}</pre>
                    </details>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-message">No tool calls recorded yet.</p>
            )}
          </section>
          <section className="research-evidence" aria-labelledby="evidence-heading">
            <h2 id="evidence-heading">Evidence collected</h2>
            {job.evidence.length ? (
              <ol className="evidence-list">
                {job.evidence.map((item) => (
                  <li key={`${item.chunk_id}-${item.document_id}`}>
                    <div className="evidence-meta">
                      <strong>
                        {documents.find((paper) => paper.id === item.document_id)?.shortTitle ??
                          sampleDocumentLabel(item.document_id)}
                        , page {item.page_number}
                      </strong>
                      <span>{item.cosine_similarity.toFixed(3)} similarity</span>
                    </div>
                    <details>
                      <summary>Read source passage</summary>
                      <p className="citation-source-text">{item.text}</p>
                    </details>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-message">Source passages appear as they are retrieved.</p>
            )}
          </section>
        </aside>
      </div>
      <CitationDrawer
        key={
          selectedCitation
            ? `${selectedCitation.chunk_id}-${selectedCitation.quote_start}`
            : "closed"
        }
        citation={selectedCitation}
        evidence={job.evidence}
        triggerRef={citationTrigger}
        onClose={closeCitation}
      />
    </section>
  );
}
