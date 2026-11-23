"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUp,
  ArrowUpRight,
  BookOpen,
  Books,
  ChatCircleText,
  CheckCircle,
  Compass,
  FilePdf,
  Plus,
  Quotes,
  ShieldCheck,
  Sparkle,
  Stop,
} from "@phosphor-icons/react";
import { useBackendReadiness } from "@/components/backend-readiness";
import { CitationBadge, CitationDrawer } from "@/components/citation-drawer";
import { useSourceLibrary } from "@/components/source-library";
import MarkdownReport from "@/components/markdown-report";
import { SAMPLE_DOCUMENTS } from "@/lib/samples";
import { selectionError } from "@/lib/request-rules";
import {
  answerQuestion,
  createResearchJob,
  ensureResearchSession,
  userFacingApiError,
  type AnswerCitation,
  type AnswerResponse,
} from "@/lib/api";

const STARTERS = [
  {
    label: "Educational QA benchmarks",
    hint: "Find the five evaluation benchmarks",
    query: "Which five benchmarks are used to evaluate the educational question-answering system?",
    ids: [SAMPLE_DOCUMENTS[0].id],
    mode: "answer",
    icon: BookOpen,
  },
  {
    label: "Nutrition model choice",
    hint: "Understand the model behind the study",
    query:
      "Which language model did the personalized nutrition system use, and why was it selected?",
    ids: [SAMPLE_DOCUMENTS[1].id],
    mode: "answer",
    icon: Sparkle,
  },
  {
    label: "Compare the three papers",
    hint: "Connect findings across all three sources",
    query: "Compare the evaluation approaches described in these papers.",
    ids: SAMPLE_DOCUMENTS.map((paper) => paper.id),
    mode: "research",
    icon: Compass,
  },
] as const;

type Mode = "answer" | "research";

export function ResearchWorkspace({ initialMode = "answer" }: { initialMode?: Mode }) {
  const router = useRouter();
  const { isReady } = useBackendReadiness();
  const {
    documents,
    selectedIds,
    setSelectedIds,
    error: libraryError,
    refresh,
  } = useSourceLibrary();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [answeredQuery, setAnsweredQuery] = useState("");
  const [selectedCitation, setSelectedCitation] = useState<AnswerCitation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const citationTrigger = useRef<HTMLButtonElement | null>(null);
  const textarea = useRef<HTMLTextAreaElement | null>(null);
  const form = useRef<HTMLFormElement | null>(null);
  const answerPanel = useRef<HTMLElement | null>(null);
  const selectionKey = selectedIds.join(",");
  const [answerScope, setAnswerScope] = useState("");
  const visibleAnswer = answerScope === selectionKey ? answer : null;

  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => {
    if (visibleAnswer)
      answerPanel.current?.scrollIntoView({
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
        block: "nearest",
      });
  }, [visibleAnswer]);

  async function run(question: string, ids: readonly string[], requestedMode: Mode) {
    if (!question.trim()) {
      setError("Write a question to start exploring your papers.");
      textarea.current?.focus();
      return;
    }
    if (!isReady) {
      setError("Wait for the research service to connect, then try again.");
      return;
    }
    const scopeError = selectionError(ids.length, requestedMode);
    if (scopeError) {
      setError(scopeError);
      return;
    }
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setSelectedIds([...ids]);
    setMode(requestedMode);
    setQuery(question);
    setBusy(true);
    setError("");
    setAnswer(null);
    setSelectedCitation(null);
    try {
      await ensureResearchSession();
      if (controller.signal.aborted) return;
      if (requestedMode === "research") {
        const job = await createResearchJob(question, [...ids], controller.signal);
        router.push(`/research/${job.job_id}`);
      } else {
        const result = await answerQuestion(question, [...ids], controller.signal);
        if (controller.signal.aborted) return;
        setAnswer(result);
        setAnswerScope(ids.join(","));
        setAnsweredQuery(question);
      }
    } catch (reason) {
      if (request.current === controller) setError(userFacingApiError(reason));
    } finally {
      if (request.current === controller) setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(query, selectedIds, mode);
  }
  function openCitation(citation: AnswerCitation, trigger: HTMLButtonElement) {
    citationTrigger.current = trigger;
    setSelectedCitation(citation);
  }
  const closeCitation = useCallback(() => setSelectedCitation(null), []);

  return (
    <div className="workspace-view page-enter">
      <header className="page-heading">
        <div>
          <span className="context-label">
            <span className="tiny-orbit" />
            Your research, connected
          </span>
          <h1>
            A clearer view of
            <br className="desktop-break" /> your research.
          </h1>
          <p className="lede">Ask better questions. Follow the evidence. Find what matters.</p>
        </div>
        <span className="heading-art" aria-hidden="true">
          <Quotes weight="duotone" size={48} />
        </span>
      </header>
      <div className="workspace-grid">
        <div className="workspace-primary">
          <form
            ref={form}
            className={`question-composer${busy ? " is-working" : ""}`}
            onSubmit={submit}
          >
            <div className="composer-modes" aria-label="Research mode">
              <button
                type="button"
                aria-pressed={mode === "answer"}
                className={mode === "answer" ? "selected" : ""}
                disabled={busy}
                onClick={() => setMode("answer")}
              >
                <ChatCircleText size={17} />
                Quick answer
              </button>
              <button
                type="button"
                aria-pressed={mode === "research"}
                className={mode === "research" ? "selected" : ""}
                disabled={busy}
                onClick={() => setMode("research")}
              >
                <Compass size={17} />
                Deep research
              </button>
            </div>
            <label className="sr-only" htmlFor="workspace-question">
              Your research question
            </label>
            <textarea
              ref={textarea}
              id="workspace-question"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                  event.preventDefault();
                  form.current?.requestSubmit();
                }
              }}
              disabled={busy}
              maxLength={4000}
              rows={4}
              placeholder={
                mode === "answer"
                  ? "What would you like to understand?"
                  : "What would you like to compare across your papers?"
              }
            />
            <div className="composer-footer">
              <span className="composer-sources">
                <Books size={17} />
                {selectedIds.length} {selectedIds.length === 1 ? "paper" : "papers"} selected
              </span>
              <div className="composer-submit">
                <span className="key-hint">Ctrl + Enter</span>
                {busy ? (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => request.current?.abort()}
                  >
                    <Stop size={15} />
                    Cancel
                  </button>
                ) : (
                  <button className="button" type="submit" disabled={!isReady}>
                    {mode === "answer" ? "Ask papers" : "Start research"}
                    <ArrowUp size={17} />
                  </button>
                )}
              </div>
            </div>
          </form>
          <p className="composer-caption">
            <ShieldCheck size={14} /> Grounded in your selected papers. Every citation is yours to
            inspect.
          </p>
          {error && (
            <div className="notice error" role="alert">
              <strong>Let&apos;s try that again.</strong>
              <p>{error}</p>
            </div>
          )}
          {busy && (
            <section className="answer-loading" role="status" aria-live="polite">
              <div className="loading-label">
                <span className="activity-indicator" />
                {mode === "answer" ? "Reading your sources..." : "Starting your research..."}
              </div>
              <div className="skeleton-line" />
              <div className="skeleton-line" />
              <div className="skeleton-line short" />
              <p>You can cancel this request at any time.</p>
            </section>
          )}
          {visibleAnswer && (
            <section
              ref={answerPanel}
              className="answer-panel reveal-in"
              aria-labelledby="answer-heading"
            >
              <div className="answer-heading">
                <span className="answer-symbol">
                  <Sparkle weight="duotone" />
                </span>
                <h2 id="answer-heading">A closer look</h2>
                <span className="subtle-pill">
                  {visibleAnswer.degraded_mode
                    ? "Evidence fallback"
                    : visibleAnswer.insufficient_evidence
                      ? "More evidence needed"
                      : "Cited answer"}
                </span>
              </div>
              <p className="answered-question">{answeredQuery}</p>
              {visibleAnswer.insufficient_evidence && (
                <p className="notice">
                  These papers did not provide enough evidence for a reliable answer. Try a narrower
                  question or select different sources.
                </p>
              )}
              {visibleAnswer.degraded_mode && (
                <p className="notice">
                  The answer service is temporarily unavailable. Your retrieved sources remain
                  available below.
                </p>
              )}
              <MarkdownReport
                content={visibleAnswer.answer}
                citations={visibleAnswer.citations}
                evidence={visibleAnswer.evidence}
                onCitationOpen={openCitation}
              />
              {visibleAnswer.citations.length > 0 && (
                <div className="answer-citations">
                  <span className="source-caption">
                    <CheckCircle size={15} /> Verified source passages
                  </span>
                  <div className="citation-list">
                    {visibleAnswer.citations.map((citation, index) => (
                      <CitationBadge
                        key={`${citation.chunk_id}-${index}`}
                        citation={citation}
                        disabled={
                          !visibleAnswer.evidence.some(
                            (item) =>
                              item.chunk_id === citation.chunk_id &&
                              item.document_id === citation.document_id,
                          )
                        }
                        onOpen={openCitation}
                      />
                    ))}
                  </div>
                </div>
              )}
              {(visibleAnswer.degraded_mode || visibleAnswer.insufficient_evidence) &&
                visibleAnswer.evidence.length > 0 && (
                  <details className="evidence-disclosure">
                    <summary>Inspect retrieved evidence ({visibleAnswer.evidence.length})</summary>
                    {visibleAnswer.evidence.map((source) => (
                      <div key={source.chunk_id}>
                        <strong>Page {source.page_number}</strong>
                        <p>{source.text}</p>
                      </div>
                    ))}
                  </details>
                )}
            </section>
          )}
          <section className="starter-section" aria-labelledby="starter-heading">
            <div className="section-heading">
              <h2 id="starter-heading">A good place to start</h2>
              <span>Try a question</span>
            </div>
            <div className="starter-list">
              {STARTERS.map(
                ({ label, hint, query: starterQuery, ids, mode: starterMode, icon: Icon }) => (
                  <button
                    key={label}
                    className="starter-button"
                    type="button"
                    aria-label={label}
                    disabled={
                      !isReady ||
                      busy ||
                      !ids.every((id) => documents.some((paper) => paper.id === id))
                    }
                    onClick={() => void run(starterQuery, ids, starterMode)}
                  >
                    <span className="starter-icon">
                      <Icon weight="duotone" />
                    </span>
                    <strong>{label}</strong>
                    <small>{hint}</small>
                    <ArrowUpRight className="starter-arrow" size={16} />
                  </button>
                ),
              )}
            </div>
          </section>
          <div className="workspace-footnote">
            <span className="footnote-rule" />
            <p>
              Good answers invite a closer look.
              <br />
              Open a source badge to see exactly where a claim comes from.
            </p>
          </div>
        </div>
        <aside className="sources-panel">
          <div className="section-heading">
            <h2>Your sources</h2>
            <span className="count-badge">{selectedIds.length}</span>
          </div>
          <p className="panel-description">Choose the papers that shape your answer.</p>
          <fieldset className="sample-picker" disabled={busy}>
            <legend className="sr-only">Selected papers</legend>
            {documents.map((paper, index) => (
              <label
                className={`sample-option${selectedIds.includes(paper.id) ? " is-selected" : ""}`}
                key={paper.id}
              >
                <span className={`paper-icon paper-color-${index % 3}`}>
                  <FilePdf size={23} weight="duotone" />
                </span>
                <span className="paper-copy">
                  <strong>{paper.shortTitle}</strong>
                  <small>{paper.detail}</small>
                  <span className="paper-type">
                    {paper.isSample ? "Sample paper" : "Private upload"}
                    {paper.pages ? ` \u00b7 ${paper.pages} pages` : ""}
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={selectedIds.includes(paper.id)}
                  aria-label={paper.title}
                  onChange={() => {
                    setSelectedIds((current) =>
                      current.includes(paper.id)
                        ? current.filter((id) => id !== paper.id)
                        : [...current, paper.id],
                    );
                    setSelectedCitation(null);
                    setError("");
                  }}
                />
              </label>
            ))}
          </fieldset>
          {libraryError && (
            <div className="notice library-notice">
              <p>{libraryError}</p>
              <button className="text-button" type="button" onClick={refresh}>
                Retry library
              </button>
            </div>
          )}
          {documents.length === 0 && !libraryError && (
            <p className="panel-description">
              No indexed papers yet. Add a searchable PDF to begin.
            </p>
          )}
          <Link className="add-source" href="/documents">
            <Plus size={17} />
            Add a PDF
            <ArrowUpRight size={15} />
          </Link>
          <div className="source-tip">
            <Quotes size={22} weight="duotone" />
            <p>One paper gives you an answer. A few can give you a new perspective.</p>
          </div>
        </aside>
      </div>
      <CitationDrawer
        key={
          selectedCitation
            ? `${selectedCitation.chunk_id}-${selectedCitation.quote_start}`
            : "closed"
        }
        citation={selectedCitation}
        evidence={visibleAnswer?.evidence ?? []}
        triggerRef={citationTrigger}
        onClose={closeCitation}
      />
    </div>
  );
}
