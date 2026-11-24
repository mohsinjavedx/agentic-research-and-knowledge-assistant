"use client";

import { useState } from "react";
import { Bookmark, Check, Copy, Download } from "lucide-react";
import { useWorkspaceMemory } from "@/components/workspace-memory";
import { useSourceLibrary } from "@/components/source-library";
import type { ResearchCitation } from "@/lib/api";

export function ReportActions({
  jobId,
  query,
  title,
  content,
  documentIds,
  citations,
  coverageWarning,
}: {
  jobId: string;
  query: string;
  title: string;
  content: string;
  documentIds: string[];
  citations: ResearchCitation[];
  coverageWarning: string | null;
}) {
  const { conversations, rememberResearch, toggleSaved } = useWorkspaceMemory();
  const { documents } = useSourceLibrary();
  const exported = `# ${title}\n\n${coverageWarning ? `> Coverage warning: ${coverageWarning.replaceAll("\n", "\n> ")}\n\n` : ""}${content}${
    citations.length
      ? "\n\n## Sources\n\n" +
        citations
          .map((citation, index) => {
            const paper = documents.find((paper) => paper.id === citation.document_id);
            return `${index + 1}. ${paper?.title ?? "Source document"} — Page ${citation.page_number}\n\n> ${citation.quote.replaceAll("\n", "\n> ")}`;
          })
          .join("\n\n")
      : ""
  }`;
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState("");
  const saved = conversations.find((item) => item.jobId === jobId)?.saved ?? false;
  async function copy() {
    try {
      await navigator.clipboard.writeText(exported);
      setCopied(true);
      setFeedback("Report copied.");
    } catch {
      setFeedback("Select the report text to copy it.");
    }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([exported], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "research-report.md";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <>
      <div className="answer-actions">
        <button className="text-button" onClick={() => void copy()}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied report" : "Copy report"}
        </button>
        <button
          className="text-button"
          onClick={() => {
            rememberResearch(query, documentIds, jobId);
            toggleSaved(jobId);
          }}
          aria-pressed={saved}
        >
          <Bookmark size={14} fill={saved ? "currentColor" : "none"} />
          {saved ? "Saved in this tab" : "Save report"}
        </button>
        <button className="text-button" onClick={download}>
          <Download size={14} />
          Download Markdown
        </button>
      </div>
      <span className="sr-only" role="status">
        {feedback}
      </span>
    </>
  );
}
