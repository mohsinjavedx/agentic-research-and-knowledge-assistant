"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowUpRight, BookOpen, FileText, Plus, X } from "lucide-react";
import { useSourceLibrary } from "@/components/source-library";
import { CitationBadge, SourceText } from "@/components/citation-drawer";
import type { AnswerCitation, AnswerResponse } from "@/lib/api";

export function ScopePicker({ disabled = false }: { disabled?: boolean }) {
  const { documents, selectedIds, setSelectedIds, error, refresh, loaded } = useSourceLibrary();
  return (
    <>
      <fieldset className="sample-picker" disabled={disabled}>
        <legend className="sr-only">Selected papers</legend>
        {!loaded && !documents.length && !error && (
          <p className="empty-message" role="status">
            Loading your document library…
          </p>
        )}
        {documents.map((paper) => (
          <label
            className={`sample-option${selectedIds.includes(paper.id) ? " is-selected" : ""}`}
            key={paper.id}
          >
            <span className="paper-icon">
              <FileText size={19} />
            </span>
            <span className="paper-copy">
              <strong>{paper.shortTitle}</strong>
              <small>
                {paper.isSample ? "Included paper" : "Private upload"}
                {paper.pages ? ` · ${paper.pages} pages` : ""}
              </small>
            </span>
            <input
              type="checkbox"
              aria-label={paper.title}
              checked={selectedIds.includes(paper.id)}
              onChange={() =>
                setSelectedIds((items) =>
                  items.includes(paper.id)
                    ? items.filter((id) => id !== paper.id)
                    : [...items, paper.id],
                )
              }
            />
          </label>
        ))}
      </fieldset>
      {error && (
        <div className="notice library-notice">
          <p>{error}</p>
          <button className="text-button" onClick={refresh}>
            Retry library
          </button>
        </div>
      )}
      {loaded && !documents.length && (
        <p className="empty-message">No indexed papers yet. Add a searchable PDF to begin.</p>
      )}
      <Link className="add-source" href="/documents">
        <Plus size={15} /> Add a PDF <ArrowUpRight size={13} />
      </Link>
    </>
  );
}

export function EvidenceList({
  answer,
  onCitationOpen,
  inspectedCitation = null,
}: {
  answer: AnswerResponse;
  onCitationOpen: (citation: AnswerCitation, trigger: HTMLButtonElement) => void;
  inspectedCitation?: AnswerCitation | null;
}) {
  const { documents } = useSourceLibrary();
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!inspectedCitation || !list.current) return;
    const panel = list.current.closest<HTMLElement>(".sources-panel");
    if (!panel?.getClientRects().length) return;
    const card = [...list.current.querySelectorAll<HTMLElement>("[data-chunk-id]")].find(
      (element) =>
        element.dataset.chunkId === inspectedCitation.chunk_id &&
        element.dataset.documentId === inspectedCitation.document_id,
    );
    const passage = card?.querySelector<HTMLDetailsElement>("details");
    if (passage) passage.open = true;
    const target = card?.querySelector("mark") ?? card;
    if (!target) return;
    // Scroll only the evidence pane, preserving the conversation's page position.
    panel.scrollTop += target.getBoundingClientRect().top - panel.getBoundingClientRect().top - 80;
  }, [inspectedCitation, answer]);
  return (
    <div className="source-evidence-list" ref={list}>
      <p className="source-score-note">
        Similarity describes retrieval relevance, not answer confidence.
      </p>
      {answer.evidence.length ? (
        answer.evidence.map((source) => {
          const isActive =
            inspectedCitation?.chunk_id === source.chunk_id &&
            inspectedCitation.document_id === source.document_id;
          const paper = documents.find((paper) => paper.id === source.document_id);
          const references = answer.citations
            .map((citation, index) => ({ citation, number: index + 1 }))
            .filter(
              ({ citation }) =>
                citation.chunk_id === source.chunk_id &&
                citation.document_id === source.document_id,
            );
          return (
            <article
              className={`source-card${references.length ? " cited" : ""}${isActive ? " is-active" : ""}`}
              key={`${source.document_id}-${source.chunk_id}`}
              data-chunk-id={source.chunk_id}
              data-document-id={source.document_id}
            >
              <div className="source-card-heading">
                <span className="source-number">
                  {references[0]?.number ?? <FileText size={12} />}
                </span>
                <strong>{paper?.shortTitle ?? "Source document"}</strong>
                <span>p. {source.page_number}</span>
              </div>
              <p className="source-excerpt">
                {source.text.slice(0, 210)}
                {source.text.length > 210 ? "…" : ""}
              </p>
              <div className="source-card-meta">
                <span>{source.cosine_similarity.toFixed(3)} similarity</span>
                {references.length > 0 && <span className="source-cited-label">Cited</span>}
              </div>
              {references.length
                ? references.map(({ citation, number }) => (
                    <CitationBadge
                      key={number}
                      citation={citation}
                      referenceNumber={number}
                      onOpen={onCitationOpen}
                    />
                  ))
                : null}
              <details>
                <summary>Read full passage</summary>
                {isActive && inspectedCitation ? (
                  <SourceText evidence={source} citation={inspectedCitation} />
                ) : (
                  <p className="citation-source-text">{source.text}</p>
                )}
              </details>
            </article>
          );
        })
      ) : (
        <p className="empty-message">No supporting passages were returned for this question.</p>
      )}
    </div>
  );
}

export function WorkspaceSources({
  answer,
  onCitationOpen,
  onHide,
  busy,
  tab,
  onTabChange,
  inspectedCitation,
}: {
  answer: AnswerResponse | null;
  onCitationOpen: (citation: AnswerCitation, trigger: HTMLButtonElement) => void;
  onHide: () => void;
  busy: boolean;
  tab: "scope" | "evidence";
  onTabChange: (tab: "scope" | "evidence") => void;
  inspectedCitation: AnswerCitation | null;
}) {
  const { selectedIds } = useSourceLibrary();
  return (
    <aside className="sources-panel" aria-label="Sources and evidence">
      <div className="sources-panel-heading">
        <BookOpen size={17} />
        <h2>Sources & evidence</h2>
        <button
          className="icon-button"
          aria-label="Hide sources"
          title="Hide sources"
          onClick={onHide}
        >
          <X size={15} />
        </button>
      </div>
      <div className="source-panel-tabs">
        <button aria-pressed={!answer || tab === "scope"} onClick={() => onTabChange("scope")}>
          Selected papers <span>{selectedIds.length}</span>
        </button>
        <button
          aria-pressed={Boolean(answer && tab === "evidence")}
          disabled={!answer}
          onClick={() => onTabChange("evidence")}
        >
          Retrieved <span>{answer?.evidence.length ?? "—"}</span>
        </button>
      </div>
      {answer && tab === "evidence" ? (
        <EvidenceList
          answer={answer}
          onCitationOpen={onCitationOpen}
          inspectedCitation={inspectedCitation}
        />
      ) : (
        <>
          <p className="panel-description">Choose the documents behind your next answer.</p>
          <ScopePicker disabled={busy} />
          <div className="source-tip">
            <BookOpen size={17} />
            <p>Choose one paper for a focused answer, or several to explore their connections.</p>
          </div>
        </>
      )}
    </aside>
  );
}
