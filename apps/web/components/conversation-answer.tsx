"use client";

import { useState } from "react";
import { Bookmark, BrainCircuit, Check, Copy, RefreshCw, Quote } from "lucide-react";
import MarkdownReport from "@/components/markdown-report";
import { useWorkspaceMemory } from "@/components/workspace-memory";
import type { AnswerCitation, AnswerResponse } from "@/lib/api";

export function ConversationAnswer({
  answer,
  question,
  id,
  onCitationOpen,
  onRetry,
  busy,
  onSources,
}: {
  answer: AnswerResponse;
  question: string;
  id: string | null;
  onCitationOpen: (citation: AnswerCitation, trigger: HTMLButtonElement) => void;
  onRetry: () => void;
  busy: boolean;
  onSources: (trigger: HTMLButtonElement) => void;
}) {
  const { conversations, toggleSaved } = useWorkspaceMemory();
  const saved = conversations.find((item) => item.id === id)?.saved ?? false;
  const [copyState, setCopyState] = useState("Copy answer");
  async function copy() {
    try {
      await navigator.clipboard.writeText(answer.answer);
      setCopyState("Copied answer");
    } catch {
      setCopyState("Select answer text to copy");
    }
  }
  return (
    <section className="conversation-answer" aria-label="Research answer">
      <h1 className="sr-only">Research conversation</h1>
      <div className="user-message">
        <span className="avatar">You</span>
        <p>{question}</p>
      </div>
      <div className="assistant-message">
        <span className="assistant-symbol">
          <BrainCircuit size={21} />
        </span>
        <div className="assistant-body">
          <div className="answer-heading">
            <h2>Research Assistant</h2>
            <span className="subtle-pill">
              {answer.degraded_mode
                ? "Evidence fallback"
                : answer.insufficient_evidence
                  ? "More evidence needed"
                  : answer.citations.length
                    ? "Source-grounded"
                    : "Uncited response"}
            </span>
          </div>
          {answer.insufficient_evidence && (
            <div className="notice">
              <strong>
                I couldn’t find enough supporting information in your selected documents.
              </strong>
              <p>
                Try rephrasing your question or adding more relevant documents to your knowledge
                base.
              </p>
            </div>
          )}
          {answer.degraded_mode && (
            <p className="notice">
              Answer generation is temporarily unavailable. The retrieved passages remain available
              for inspection.
            </p>
          )}
          <MarkdownReport
            content={answer.answer}
            citations={answer.citations}
            evidence={answer.evidence}
            onCitationOpen={onCitationOpen}
          />
          <div className="answer-actions">
            <button
              className="text-button"
              aria-label={copyState}
              title={copyState}
              onClick={() => void copy()}
            >
              {copyState === "Copied answer" ? <Check size={14} /> : <Copy size={14} />}
              <span>{copyState}</span>
            </button>
            <button className="text-button" disabled={busy} onClick={onRetry}>
              <RefreshCw size={14} /> Ask again
            </button>
            {id && (
              <button
                className={`text-button${saved ? " accent-text" : ""}`}
                aria-label={saved ? "Unsave answer" : "Save answer"}
                title="Save in this tab only"
                aria-pressed={saved}
                onClick={() => toggleSaved(id)}
              >
                <Bookmark size={14} fill={saved ? "currentColor" : "none"} />
                {saved ? "Saved in this tab" : "Save"}
              </button>
            )}
            <button
              className="text-button answer-source-count"
              onClick={(event) => onSources(event.currentTarget)}
            >
              <Quote size={14} />
              {answer.citations.length} {answer.citations.length === 1 ? "citation" : "citations"}
            </button>
          </div>
          <span className="sr-only" role="status">
            {copyState === "Copied answer" ? "Answer copied to clipboard." : ""}
          </span>
        </div>
      </div>
    </section>
  );
}
