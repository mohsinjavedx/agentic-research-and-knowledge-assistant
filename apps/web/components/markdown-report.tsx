"use client";

import ReactMarkdown from "react-markdown";
import { createContext, useContext, type ReactNode } from "react";
import remarkGfm from "remark-gfm";
import { CitationBadge } from "@/components/citation-drawer";
import type { AnswerEvidence, ResearchCitation } from "@/lib/api";

type CitationContext = {
  citations: ResearchCitation[];
  evidence: AnswerEvidence[];
  onCitationOpen?: (citation: ResearchCitation, trigger: HTMLButtonElement) => void;
};
const CitationContext = createContext<CitationContext>({ citations: [], evidence: [] });

function MarkdownLink({ href, children }: { href?: string; children?: ReactNode }) {
  const { citations, evidence, onCitationOpen } = useContext(CitationContext);
  const match = /^#citation-(\d+)$/.exec(href ?? "");
  const citation = match ? citations[Number(match[1])] : null;
  if (citation && onCitationOpen)
    return (
      <CitationBadge
        citation={citation}
        referenceNumber={Number(match![1]) + 1}
        disabled={
          !evidence.some(
            (item) =>
              item.chunk_id === citation.chunk_id && item.document_id === citation.document_id,
          )
        }
        onOpen={onCitationOpen}
      />
    );
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

// Stable component identity keeps inline citation trigger DOM/focus across rerenders.
const markdownComponents = {
  a: MarkdownLink,
  // Retrieved/model text is untrusted. Images can leak private content through their URLs.
  img: ({ alt }: { alt?: string }) => (
    <span className="muted">{alt ? `[Image omitted: ${alt}]` : "[Image omitted]"}</span>
  ),
};

export default function MarkdownReport({
  content,
  citations = [],
  evidence = [],
  onCitationOpen,
}: {
  content: string;
  citations?: ResearchCitation[];
  evidence?: AnswerEvidence[];
  onCitationOpen?: (citation: ResearchCitation, trigger: HTMLButtonElement) => void;
}) {
  // Exact claim matches receive a citation directly after the supporting statement.
  // Claims split by Markdown formatting remain available in the source list.
  let citedContent = content;
  if (onCitationOpen) {
    const insertions = citations
      .flatMap((citation, index) => {
        const start = content.indexOf(citation.claim);
        return start < 0 ? [] : [{ end: start + citation.claim.length, index }];
      })
      .sort((a, b) => b.end - a.end);
    for (const { end, index } of insertions)
      citedContent = `${citedContent.slice(0, end)} [source](#citation-${index})${citedContent.slice(end)}`;
  }
  return (
    <CitationContext.Provider value={{ citations, evidence, onCitationOpen }}>
      <div className="markdown-content">
        <ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {citedContent}
        </ReactMarkdown>
      </div>
    </CitationContext.Provider>
  );
}
