"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { Check, Copy, FileText, Quotes, X } from "@phosphor-icons/react";
import { sampleDocumentLabel } from "@/lib/samples";
import { useSourceLibrary } from "@/components/source-library";
import type { AnswerEvidence, ResearchCitation } from "@/lib/api";

export function CitationBadge({
  citation,
  disabled = false,
  onOpen,
}: {
  citation: ResearchCitation;
  disabled?: boolean;
  onOpen: (citation: ResearchCitation, trigger: HTMLButtonElement) => void;
}) {
  const { documents } = useSourceLibrary();
  const source = documents.find((item) => item.id === citation.document_id);
  const label = source?.isSample
    ? sampleDocumentLabel(citation.document_id)
    : (source?.shortTitle ?? `Source ${citation.document_id.slice(0, 8)}`);
  return (
    <button
      className="citation-badge"
      type="button"
      disabled={disabled}
      aria-label={`Open ${source?.shortTitle ?? label}, page ${citation.page_number}`}
      onClick={(event) => onOpen(citation, event.currentTarget)}
    >
      <FileText size={13} />
      {label}, p. {citation.page_number}
    </button>
  );
}

function SourceText({
  evidence,
  citation,
}: {
  evidence: AnswerEvidence;
  citation: ResearchCitation;
}) {
  // API offsets count Unicode code points; JavaScript slice counts UTF-16 units.
  const points = Array.from(evidence.text);
  const valid =
    citation.quote_start >= 0 &&
    citation.quote_end <= points.length &&
    points.slice(citation.quote_start, citation.quote_end).join("") === citation.quote;
  if (!valid)
    return (
      <>
        <p className="notice">
          Exact highlight unavailable: the supplied quote does not match this source range.
        </p>
        <div className="citation-source-text">{evidence.text}</div>
      </>
    );
  return (
    <div className="citation-source-text">
      {points.slice(0, citation.quote_start).join("")}
      <mark>{citation.quote}</mark>
      {points.slice(citation.quote_end).join("")}
    </div>
  );
}

export function CitationDrawer({
  citation,
  evidence,
  triggerRef,
  onClose,
}: {
  citation: ResearchCitation | null;
  evidence: AnswerEvidence[];
  triggerRef: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const { documents } = useSourceLibrary();
  const [copyState, setCopyState] = useState("Copy quote");
  useEffect(() => {
    if (!citation) return;
    const element = dialog.current;
    const trigger = triggerRef.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    element?.showModal();
    element?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
      trigger?.focus();
    };
  }, [citation, triggerRef]);
  const source = citation
    ? evidence.find(
        (item) => item.chunk_id === citation.chunk_id && item.document_id === citation.document_id,
      )
    : null;
  const paper = documents.find((item) => item.id === citation?.document_id);
  if (!citation) return null;
  async function copyQuote() {
    try {
      await navigator.clipboard.writeText(citation!.quote);
      setCopyState("Copied");
    } catch {
      setCopyState("Select the quote to copy");
    }
  }
  return (
    <dialog
      ref={dialog}
      className="citation-drawer"
      aria-labelledby="citation-drawer-title"
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = event.currentTarget.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), [tabindex="0"]',
        );
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        if (
          event.target === event.currentTarget &&
          (event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom)
        )
          onClose();
      }}
    >
      <div className="drawer-heading">
        <div>
          <span className="context-label">
            <Quotes size={16} />
            Behind the answer
          </span>
          <h2 id="citation-drawer-title">Source details</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Close source details"
          onClick={onClose}
          autoFocus
        >
          <X />
        </button>
      </div>
      <div className="drawer-paper">
        <span className="paper-icon paper-color-0">
          <FileText size={26} weight="duotone" />
        </span>
        <div>
          <strong>{paper?.title ?? `Source ${citation.document_id.slice(0, 8)}`}</strong>
          <span>{paper?.detail ?? "Private source"}</span>
        </div>
      </div>
      <dl className="source-stats">
        <div>
          <dt>Source page</dt>
          <dd>{citation.page_number}</dd>
        </div>
        <div>
          <dt>Cosine similarity</dt>
          <dd>{source ? source.cosine_similarity.toFixed(3) : "Unavailable"}</dd>
        </div>
      </dl>
      <section className="claim-section">
        <h3>Claim in the answer</h3>
        <p>{citation.claim}</p>
      </section>
      <div className="section-heading">
        <h3>Original source passage</h3>
        <button
          aria-label={copyState}
          className="text-button copy-button"
          type="button"
          onClick={() => void copyQuote()}
        >
          {copyState === "Copied" ? <Check size={14} /> : <Copy size={14} />}
          <span role="status">{copyState}</span>
        </button>
      </div>
      <p className="source-explainer">
        The highlight shows the exact supporting quote. Similarity measures retrieval relevance, not
        factual certainty.
      </p>
      {source ? (
        <SourceText evidence={source} citation={citation} />
      ) : (
        <p className="notice error" role="alert">
          This source passage was not included in the response.
        </p>
      )}
      <p className="drawer-footnote">Read the surrounding passage to keep the claim in context.</p>
    </dialog>
  );
}
