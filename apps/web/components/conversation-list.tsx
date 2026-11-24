"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Bookmark,
  BrainCircuit,
  Clock3,
  History,
  MessageSquare,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useWorkspaceMemory, type Conversation } from "@/components/workspace-memory";
import { useSourceLibrary } from "@/components/source-library";
import { ModalDialog } from "@/components/modal-dialog";

function groupLabel(createdAt: string): string {
  const today = new Date();
  const date = new Date(createdAt);
  const day = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const then = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  const days = Math.floor((day - then) / 86_400_000);
  return days === 0 ? "Today" : days === 1 ? "Yesterday" : days < 7 ? "Previous 7 days" : "Older";
}

export function ConversationList({ savedOnly = false }: { savedOnly?: boolean }) {
  const router = useRouter();
  const { conversations, activate, newResearch, remove, toggleSaved } = useWorkspaceMemory();
  const { documents, loaded, setSelectedIds } = useSourceLibrary();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [candidate, setCandidate] = useState<Conversation | null>(null);
  const entries = conversations.filter(
    (item) =>
      (!savedOnly || item.saved) &&
      item.query.toLowerCase().includes(query.toLowerCase()) &&
      (kind === "all" || kind === item.kind),
  );
  function open(item: Conversation) {
    if (item.kind === "research" && item.jobId) {
      router.push(`/research/${item.jobId}`);
      return;
    }
    setSelectedIds(item.documentIds.filter((id) => documents.some((paper) => paper.id === id)));
    activate(item.id);
    router.push("/workspace");
  }
  return (
    <section className="collection-page page-enter">
      <header className="page-heading">
        <div>
          <span className="context-label">
            {savedOnly ? <Bookmark size={15} /> : <History size={15} />}In this tab
          </span>
          <h1>{savedOnly ? "Saved research" : "Recent conversations"}</h1>
          <p>
            {savedOnly
              ? "Keep the answers you want to return to while you work."
              : "Pick up a question, revisit an answer, or explore another connection."}
          </p>
        </div>
        <Link className="button" href="/workspace" onClick={newResearch}>
          <Plus size={16} />
          New research
        </Link>
      </header>
      <p className="collection-privacy-note">
        <Clock3 size={15} />
        <span>
          This is activity from this open tab, held only in memory. Refreshing clears it. Research
          run links remain subject to your session’s access and expiry.
          {savedOnly &&
            " The tab keeps the 32 most recent items, including bookmarks; new activity can remove older items."}
        </span>
      </p>
      <div className="collection-toolbar">
        <label className="search-field">
          <Search size={15} />
          <input
            type="search"
            aria-label="Search conversations"
            placeholder="Search your questions…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className="filter-tabs" aria-label="Conversation type">
          {[
            ["all", "All activity"],
            ["answer", "Answers"],
            ["research", "Research runs"],
          ].map(([value, label]) => (
            <button key={value} aria-pressed={kind === value} onClick={() => setKind(value)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {entries.length ? (
        ["Today", "Yesterday", "Previous 7 days", "Older"].map((group) => {
          const items = entries.filter((item) => groupLabel(item.createdAt) === group);
          return items.length ? (
            <section className="history-group" key={group}>
              <h2>{group}</h2>
              {items.map((item) => (
                <article className="conversation-row" key={item.id}>
                  <span className="conversation-icon">
                    {item.kind === "answer" ? (
                      <MessageSquare size={17} />
                    ) : (
                      <BrainCircuit size={17} />
                    )}
                  </span>
                  <button
                    className="conversation-row-main"
                    disabled={!loaded && item.kind === "answer"}
                    onClick={() => open(item)}
                  >
                    <strong>{item.query}</strong>
                    <small>
                      {item.kind === "research"
                        ? "Research run"
                        : item.answer?.degraded_mode
                          ? "Evidence fallback"
                          : item.answer?.insufficient_evidence
                            ? "Insufficient evidence"
                            : item.answer?.citations.length
                              ? "Cited answer snapshot"
                              : "Uncited answer snapshot"}{" "}
                      · {item.documentIds.length}{" "}
                      {item.documentIds.length === 1 ? "document" : "documents"} ·{" "}
                      {new Date(item.createdAt).toLocaleTimeString([], {
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </small>
                  </button>
                  <button
                    className="icon-button"
                    aria-label={item.saved ? `Unsave ${item.query}` : `Save ${item.query}`}
                    title={item.saved ? "Remove bookmark" : "Save in this tab"}
                    aria-pressed={item.saved}
                    onClick={() => toggleSaved(item.id)}
                  >
                    <Bookmark size={15} fill={item.saved ? "currentColor" : "none"} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`Delete conversation: ${item.query}`}
                    title="Delete from this tab"
                    onClick={() => setCandidate(item)}
                  >
                    <Trash2 size={15} />
                  </button>
                </article>
              ))}
            </section>
          ) : null;
        })
      ) : (
        <div className="empty-state">
          {savedOnly ? <Bookmark size={36} /> : <History size={36} />}
          <h2>
            {savedOnly ? "No saved research in this tab." : "Your next question starts the story."}
          </h2>
          <p>
            {query || kind !== "all"
              ? "Try a different search or filter."
              : savedOnly
                ? "Save an answer or bookmark a research run to find it here. Bookmarks last until you refresh or clear this tab."
                : "Ask a question in the workspace. Your activity will appear here while this tab stays open."}
          </p>
          <Link className="button secondary" href="/workspace">
            Open workspace
          </Link>
        </div>
      )}
      <ModalDialog
        open={Boolean(candidate)}
        title="Delete conversation?"
        onClose={() => setCandidate(null)}
      >
        <p>
          Remove this question and its answer from this tab? Your source documents and server-side
          research run are not deleted.
        </p>
        <div className="modal-actions">
          <button className="button secondary" onClick={() => setCandidate(null)}>
            Cancel
          </button>
          <button
            className="button danger"
            onClick={() => {
              if (candidate) remove(candidate.id);
              setCandidate(null);
            }}
          >
            Delete conversation
          </button>
        </div>
      </ModalDialog>
    </section>
  );
}
