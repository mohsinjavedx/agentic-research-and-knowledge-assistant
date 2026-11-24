"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ArrowUp,
  BookOpen,
  BrainCircuit,
  ChevronDown,
  FileText,
  Files,
  MessageSquare,
  Network,
  Paperclip,
  PanelRightOpen,
  ShieldCheck,
  Square,
} from "lucide-react";
import { useBackendReadiness } from "@/components/backend-readiness";
import { CitationDrawer } from "@/components/citation-drawer";
import { ConversationAnswer } from "@/components/conversation-answer";
import { useSourceLibrary } from "@/components/source-library";
import { useWorkspaceMemory } from "@/components/workspace-memory";
import { ScopePicker, WorkspaceSources, EvidenceList } from "@/components/workspace-sources";
import { ModalDialog } from "@/components/modal-dialog";
import { SAMPLE_DOCUMENTS } from "@/lib/samples";
import { selectionError } from "@/lib/request-rules";
import {
  answerQuestion,
  createResearchJob,
  ensureResearchSession,
  userFacingApiError,
  type AnswerCitation,
} from "@/lib/api";

const TASK_STARTERS = [
  {
    query: "Summarize my uploaded documents.",
    label: "Summarize my documents",
    hint: "Bring the main ideas into focus",
    icon: FileText,
  },
  {
    query: "Find the key concepts across my research papers.",
    label: "Find key concepts",
    hint: "Connect ideas across selected papers",
    icon: BookOpen,
  },
  {
    query: "Compare the main arguments in my documents.",
    label: "Compare main arguments",
    hint: "Explore agreements and differences",
    icon: Network,
  },
  {
    query: "Find evidence supporting a particular claim.",
    label: "Find supporting evidence",
    hint: "Start here, then add your specific claim",
    icon: BrainCircuit,
  },
] as const;
const SAMPLE_STARTERS = [
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
    icon: FileText,
  },
  {
    label: "Compare the three papers",
    hint: "Connect evaluation methods across sources",
    query: "Compare the evaluation approaches described in these papers.",
    ids: SAMPLE_DOCUMENTS.map((paper) => paper.id),
    mode: "research",
    icon: BrainCircuit,
  },
  {
    label: "Medical retrieval strategies",
    hint: "Explore how the system finds evidence",
    query:
      "Which of the medical system’s retrieval approaches performed best according to the authors, and why?",
    ids: [SAMPLE_DOCUMENTS[2].id],
    mode: "answer",
    icon: Network,
  },
] as const;
type Mode = "answer" | "research";

export function ResearchWorkspace({ initialMode = "answer" }: { initialMode?: Mode }) {
  const { activeId, draftVersion } = useWorkspaceMemory();
  return <WorkspaceView key={activeId ?? `new-${draftVersion}`} initialMode={initialMode} />;
}

function WorkspaceView({ initialMode }: { initialMode: Mode }) {
  const router = useRouter();
  const { isReady } = useBackendReadiness();
  const { documents, selectedIds, setSelectedIds, loaded } = useSourceLibrary();
  const scopeReady =
    loaded ||
    (selectedIds.length > 0 &&
      selectedIds.every((id) => documents.some((paper) => paper.id === id)));
  const { conversations, activeId, rememberAnswer, rememberResearch } = useWorkspaceMemory();
  const active = conversations.find((item) => item.id === activeId && item.kind === "answer");
  const [mode, setMode] = useState<Mode>(initialMode);
  const [query, setQuery] = useState(active?.query ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(true);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<AnswerCitation | null>(null);
  const [inspectedCitation, setInspectedCitation] = useState<AnswerCitation | null>(null);
  const [sourceTab, setSourceTab] = useState<"scope" | "evidence">(
    active?.answer ? "evidence" : "scope",
  );
  const request = useRef<AbortController | null>(null);
  const running = useRef(false);
  const citationTrigger = useRef<HTMLButtonElement | null>(null);
  const evidenceTrigger = useRef<HTMLButtonElement | null>(null);
  const textarea = useRef<HTMLTextAreaElement | null>(null);
  const form = useRef<HTMLFormElement | null>(null);
  const visibleAnswer =
    active &&
    active.documentIds.length === selectedIds.length &&
    active.documentIds.every((id) => selectedIds.includes(id))
      ? (active.answer ?? null)
      : null;
  useEffect(() => () => request.current?.abort(), []);
  const closeCitation = useCallback(() => setSelectedCitation(null), [setSelectedCitation]);
  function openCitation(citation: AnswerCitation, trigger: HTMLButtonElement) {
    citationTrigger.current = trigger;
    setSourcesOpen(true);
    setSourceTab("evidence");
    setInspectedCitation({ ...citation });
    setSelectedCitation(citation);
  }
  async function run(question: string, ids: readonly string[], requestedMode: Mode) {
    if (running.current) return;
    if (!question.trim()) {
      setError("Write a question to start exploring your papers.");
      textarea.current?.focus();
      return;
    }
    if (!isReady) {
      setError("Wait for the research service to connect, then try again.");
      return;
    }
    if (!scopeReady) {
      setError("Wait for the document library to load, then try again.");
      return;
    }
    const scopeError = selectionError(ids.length, requestedMode);
    if (scopeError) {
      setError(scopeError);
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    running.current = true;
    setBusy(true);
    setError("");
    setSelectedCitation(null);
    try {
      await ensureResearchSession();
      if (controller.signal.aborted) return;
      if (requestedMode === "research") {
        const job = await createResearchJob(question, [...ids], controller.signal);
        if (controller.signal.aborted) return;
        rememberResearch(question, [...ids], job.job_id);
        router.push(`/research/${job.job_id}`);
      } else {
        const answer = await answerQuestion(question, [...ids], controller.signal);
        if (!controller.signal.aborted) rememberAnswer(question, [...ids], answer);
      }
    } catch (reason) {
      if (request.current === controller) setError(userFacingApiError(reason));
    } finally {
      if (request.current === controller) {
        setBusy(false);
        running.current = false;
      }
    }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(query, selectedIds, mode);
  }
  return (
    <div
      className={`workspace-view page-enter${sourcesOpen ? "" : " sources-hidden"}${visibleAnswer ? " has-answer" : ""}`}
    >
      <div className="workspace-page-bar">
        <span>
          <MessageSquare size={15} />{" "}
          {mode === "answer" ? "Research conversation" : "Agentic research"}
        </span>
        <button
          className="text-button desktop-source-toggle"
          onClick={() => setSourcesOpen((value) => !value)}
          aria-pressed={sourcesOpen}
        >
          <PanelRightOpen size={15} />
          <span>{sourcesOpen ? "Sources" : "Show sources"}</span>
        </button>
        <button
          className="text-button compact-source-toggle"
          aria-haspopup="dialog"
          onClick={(event) => {
            if (visibleAnswer) {
              evidenceTrigger.current = event.currentTarget;
              setEvidenceOpen(true);
            } else setScopeOpen(true);
          }}
        >
          <PanelRightOpen size={15} />
          Sources
        </button>
      </div>
      <div className="workspace-grid">
        <div className="workspace-primary">
          {visibleAnswer && active ? (
            <ConversationAnswer
              answer={visibleAnswer}
              question={active.query}
              id={active.id}
              busy={busy || !isReady || !scopeReady}
              onCitationOpen={openCitation}
              onRetry={() => void run(active.query, active.documentIds, "answer")}
              onSources={(trigger) => {
                evidenceTrigger.current = trigger;
                setEvidenceOpen(true);
              }}
            />
          ) : (
            <header className="workspace-intro">
              <span className="workspace-intro-symbol">
                <BrainCircuit size={26} />
              </span>
              <span className="context-label">A clearer path through your knowledge</span>
              <h1>What would you like to research?</h1>
              <p>
                Ask questions across your documents.
                <br />
                Discover answers with evidence you can follow.
              </p>
            </header>
          )}
          {!visibleAnswer && (
            <section className="starter-section" aria-label="Suggested research questions">
              <div className="starter-list">
                {TASK_STARTERS.map(({ query: prompt, label, hint, icon: Icon }) => (
                  <button
                    className="starter-button"
                    key={prompt}
                    aria-label={prompt}
                    disabled={busy || !scopeReady || !selectedIds.length}
                    onClick={() => {
                      setQuery(prompt);
                      setError("");
                      textarea.current?.focus();
                    }}
                  >
                    <Icon size={18} />
                    <strong>{label}</strong>
                    <small>{hint}</small>
                    <ArrowRight size={14} className="starter-arrow" />
                  </button>
                ))}
              </div>
              <p className="suggestion-hint">
                Uses your selected papers. Edit the question, then send when you’re ready.
              </p>
              <details className="sample-examples">
                <summary>Included-paper examples</summary>
                <p>
                  Choosing an example switches the selected papers to its included sample sources.
                </p>
                <div className="sample-example-list">
                  {SAMPLE_STARTERS.map(
                    ({ label, query: starterQuery, ids, mode: starterMode, icon: Icon }) => (
                      <button
                        className="sample-example-button"
                        key={label}
                        aria-label={label}
                        disabled={
                          busy || !ids.every((id) => documents.some((paper) => paper.id === id))
                        }
                        onClick={() => {
                          setSelectedIds([...ids]);
                          setMode(starterMode);
                          setQuery(starterQuery);
                          setError("");
                          textarea.current?.focus();
                        }}
                      >
                        <Icon size={18} />
                        <span>{label}</span>
                      </button>
                    ),
                  )}
                </div>
              </details>
            </section>
          )}
          {busy && (
            <section className="answer-loading" role="status" aria-live="polite">
              <div className="loading-label">
                <span className="activity-indicator" />
                {mode === "answer" ? "Reading your sources…" : "Starting your research…"}
              </div>
              <div className="skeleton-line" />
              <div className="skeleton-line" />
              <div className="skeleton-line short" />
              <p>
                The result will appear when it is ready. Cancel stops waiting for this response.
              </p>
            </section>
          )}
          {error && (
            <div className="notice error" role="alert">
              <strong>Let’s try that again.</strong>
              <p>{error}</p>
            </div>
          )}
          <div className="composer-area">
            <form
              ref={form}
              className={`question-composer${busy ? " is-working" : ""}`}
              onSubmit={submit}
            >
              <div className="composer-modes" aria-label="Research mode">
                <button
                  type="button"
                  aria-pressed={mode === "answer"}
                  disabled={busy}
                  className={mode === "answer" ? "selected" : ""}
                  onClick={() => setMode("answer")}
                >
                  <MessageSquare size={14} /> Quick answer
                </button>
                <button
                  type="button"
                  aria-pressed={mode === "research"}
                  disabled={busy}
                  className={mode === "research" ? "selected" : ""}
                  onClick={() => setMode("research")}
                >
                  <BrainCircuit size={14} /> Deep research
                </button>
              </div>
              <label className="sr-only" htmlFor="workspace-question">
                Your research question
              </label>
              <textarea
                id="workspace-question"
                ref={textarea}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  event.currentTarget.style.height = "auto";
                  event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 140)}px`;
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    form.current?.requestSubmit();
                  }
                }}
                disabled={busy}
                maxLength={4000}
                rows={3}
                placeholder={
                  mode === "answer"
                    ? "Ask anything about your documents…"
                    : "What would you like to compare across your papers?"
                }
              />
              <div className="composer-footer">
                <div className="composer-tools">
                  <Link
                    href="/documents"
                    className="icon-button"
                    aria-label="Add a PDF"
                    title="Upload a PDF to your library"
                  >
                    <Paperclip size={17} />
                  </Link>
                  <span className="tool-divider" />
                  <button
                    className="composer-sources"
                    type="button"
                    disabled={busy}
                    onClick={() => setScopeOpen(true)}
                  >
                    <Files size={14} />
                    {selectedIds.length} {selectedIds.length === 1 ? "paper" : "papers"}
                    <ChevronDown size={12} />
                  </button>
                </div>
                <div className="composer-submit">
                  {query.length > 0 && <span className="character-count">{query.length}/4000</span>}
                  {busy ? (
                    <button
                      type="button"
                      className="button secondary"
                      title="Stop waiting for this response"
                      onClick={() => request.current?.abort()}
                    >
                      <Square size={13} />
                      Cancel
                    </button>
                  ) : (
                    <button
                      className="button send-button"
                      type="submit"
                      disabled={!isReady || !scopeReady || !query.trim()}
                    >
                      {mode === "answer" ? "Ask papers" : "Start research"}
                      <ArrowUp size={16} />
                    </button>
                  )}
                </div>
              </div>
            </form>
            <p className="composer-caption">
              <ShieldCheck size={12} />
              <span>Each question searches your selected papers independently.</span>
              <span className="composer-key-hint">
                Enter to send <span>·</span> Shift + Enter for a new line
              </span>
            </p>
          </div>
        </div>
        {sourcesOpen && (
          <WorkspaceSources
            key={active?.id ?? "new"}
            answer={visibleAnswer}
            busy={busy}
            tab={sourceTab}
            onTabChange={setSourceTab}
            inspectedCitation={inspectedCitation}
            onCitationOpen={openCitation}
            onHide={() => setSourcesOpen(false)}
          />
        )}
      </div>
      <ModalDialog open={scopeOpen} title="Select sources" onClose={() => setScopeOpen(false)}>
        <p>Choose which papers this question can use.</p>
        <ScopePicker disabled={busy} />
        <div className="modal-actions">
          <button className="button" onClick={() => setScopeOpen(false)}>
            Use selected papers
          </button>
        </div>
      </ModalDialog>
      <ModalDialog
        open={evidenceOpen}
        title="Sources & evidence"
        className="evidence-modal"
        onClose={() => setEvidenceOpen(false)}
      >
        {visibleAnswer && (
          <EvidenceList
            answer={visibleAnswer}
            onCitationOpen={(citation, trigger) => {
              setEvidenceOpen(false);
              openCitation(citation, evidenceTrigger.current ?? trigger);
            }}
          />
        )}
      </ModalDialog>
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
