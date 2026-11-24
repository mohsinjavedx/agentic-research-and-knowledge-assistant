"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpRight,
  CircleCheck,
  Database,
  FileText,
  Info,
  Search,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useSourceLibrary, type LibraryDocument } from "@/components/source-library";
import { DocumentUpload } from "@/components/document-upload";
import { ModalDialog } from "@/components/modal-dialog";
import { userFacingApiError } from "@/lib/api";

type Filter = "all" | "private" | "sample";
export function DocumentLibrary({ knowledge = false }: { knowledge?: boolean }) {
  const {
    documents,
    selectedIds,
    setSelectedIds,
    deletePrivateDocument,
    deletingIds,
    mutationError,
    loaded,
    error: libraryError,
    refresh,
  } = useSourceLibrary();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [deleting, setDeleting] = useState(false);
  const [candidate, setCandidate] = useState<LibraryDocument | null>(null);
  const [detail, setDetail] = useState<LibraryDocument | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const confirming = useRef(false);
  const selection = useRef<HTMLInputElement>(null);
  // Reconcile after returning from an interrupted/uncertain server operation.
  useEffect(() => {
    refresh();
  }, [refresh]);
  const displayed = useMemo(
    () =>
      documents.filter(
        (paper) =>
          `${paper.title} ${paper.filename ?? ""}`.toLowerCase().includes(query.toLowerCase()) &&
          (filter === "all" || (filter === "sample" ? paper.isSample : !paper.isSample)),
      ),
    [documents, query, filter],
  );
  const selectedCount = displayed.filter((paper) => selectedIds.includes(paper.id)).length;
  const allSelected = displayed.length > 0 && selectedCount === displayed.length;
  useEffect(() => {
    if (selection.current) selection.current.indeterminate = selectedCount > 0 && !allSelected;
  }, [selectedCount, allSelected]);
  async function confirmDelete() {
    if (!candidate || candidate.isSample || confirming.current) return;
    confirming.current = true;
    setDeleting(true);
    setError("");
    try {
      await deletePrivateDocument(candidate.id);
      setSuccess(`${candidate.title} was removed from your library.`);
      setCandidate(null);
    } catch (reason) {
      setError(userFacingApiError(reason));
    } finally {
      setDeleting(false);
      confirming.current = false;
    }
  }
  return (
    <section className="documents-page page-enter">
      <header className="page-heading">
        <div>
          <span className="context-label">
            {knowledge ? <Database size={15} /> : <FileText size={15} />}
            {knowledge ? "Your research, in scope" : "Your research collection"}
          </span>
          <h1>{knowledge ? "Knowledge base" : "My documents"}</h1>
          <p>
            {knowledge
              ? "Choose the documents behind your questions. Keep your evidence focused."
              : "Manage your uploaded files and research knowledge."}
          </p>
        </div>
        <DocumentUpload
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          onSuccess={(message) => {
            setSuccess(message);
            setError("");
          }}
        />
      </header>
      <dl className="document-overview">
        <div>
          <dt>Available documents</dt>
          <dd>{loaded ? documents.length : "—"}</dd>
        </div>
        <div>
          <dt>Private uploads</dt>
          <dd>{loaded ? documents.filter((paper) => !paper.isSample).length : "—"}</dd>
        </div>
        <div>
          <dt>Selected for research</dt>
          <dd>{loaded ? selectedIds.length : "—"}</dd>
        </div>
      </dl>
      {success && (
        <p className="notice success" role="status">
          <CircleCheck size={16} />
          {success}
        </p>
      )}
      {error && !candidate && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {libraryError && (
        <div className="notice" role="alert">
          <p>{libraryError}</p>
          <button className="text-button" onClick={refresh}>
            Retry library
          </button>
        </div>
      )}
      <div className="documents-toolbar">
        <label className="search-field">
          <Search size={15} />
          <input
            type="search"
            aria-label="Search documents"
            placeholder="Search your documents…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            autoFocus={knowledge}
          />
        </label>
        <div className="filter-tabs" aria-label="Document filter">
          {(
            [
              ["all", "All documents"],
              ["private", "My uploads"],
              ["sample", "Included"],
            ] as const
          ).map(([value, label]) => (
            <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {!loaded && documents.length === 0 && !libraryError ? (
        <div role="status" aria-label="Loading documents">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line short" />
        </div>
      ) : (
        <>
          <table className="document-table">
            <thead>
              <tr>
                <th className="checkbox-column">
                  <input
                    ref={selection}
                    type="checkbox"
                    aria-label="Select all displayed documents"
                    checked={allSelected}
                    disabled={!displayed.length}
                    onChange={() =>
                      setSelectedIds((items) =>
                        allSelected
                          ? items.filter((id) => !displayed.some((paper) => paper.id === id))
                          : [...new Set([...items, ...displayed.map((paper) => paper.id)])],
                      )
                    }
                  />
                </th>
                <th>Document</th>
                <th className="metadata-column">Type</th>
                <th className="metadata-column">Pages</th>
                <th className="status-column">Status</th>
                <th className="actions-column">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((paper) => (
                <tr
                  className={`document-row${selectedIds.includes(paper.id) ? " is-selected" : ""}`}
                  key={paper.id}
                >
                  <td className="checkbox-column">
                    <input
                      type="checkbox"
                      aria-label={`Select ${paper.title}`}
                      checked={selectedIds.includes(paper.id)}
                      onChange={() =>
                        setSelectedIds((items) =>
                          items.includes(paper.id)
                            ? items.filter((id) => id !== paper.id)
                            : [...items, paper.id],
                        )
                      }
                    />
                  </td>
                  <td>
                    <div className="document-file">
                      <span className="paper-icon">
                        <FileText size={19} />
                      </span>
                      <div>
                        <button className="document-title" onClick={() => setDetail(paper)}>
                          {paper.title}
                        </button>
                        <small>
                          {paper.isSample ? "Included paper" : "Private upload"}
                          {paper.pages ? ` · ${paper.pages} pages` : ""}
                        </small>
                      </div>
                    </div>
                  </td>
                  <td className="metadata-column">PDF</td>
                  <td className="metadata-column">{paper.pages ?? "—"}</td>
                  <td className="status-column">
                    <span className="ready-badge">Ready</span>
                  </td>
                  <td className="actions-column">
                    <div className="document-row-actions">
                      <button
                        className="icon-button"
                        aria-label={`Details for ${paper.title}`}
                        title="View details"
                        onClick={() => setDetail(paper)}
                      >
                        <Info size={15} />
                      </button>
                      {!paper.isSample && (
                        <button
                          className="icon-button"
                          aria-label={`Delete ${paper.title}`}
                          disabled={deletingIds.includes(paper.id)}
                          title="Delete document"
                          onClick={() => {
                            setError("");
                            setCandidate(paper);
                          }}
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!displayed.length && (
            <div className="empty-state">
              <FileText size={34} />
              <h2>
                {documents.length
                  ? "No documents match your search."
                  : "Your knowledge starts here."}
              </h2>
              <p>
                {documents.length
                  ? "Try another name or change the filter."
                  : "Upload a searchable PDF to begin exploring its ideas."}
              </p>
            </div>
          )}
        </>
      )}
      <div className="scope-summary">
        <span>
          <strong>{selectedIds.length}</strong>{" "}
          {selectedIds.length === 1 ? "document" : "documents"} selected for your next question
        </span>
        <Link className="button secondary" href="/workspace">
          Open workspace <ArrowUpRight size={14} />
        </Link>
      </div>
      {mutationError && !error && !uploadOpen && (
        <p className="notice error" role="alert">
          {mutationError}
        </p>
      )}
      {deletingIds.length > 0 && (
        <p className="notice" role="status">
          Finishing confirmed document deletion…
        </p>
      )}
      <p className="documents-footnote">
        <ShieldCheck size={13} />
        Only ready, indexed documents are listed. Private uploads expire within 24 hours.
      </p>
      <ModalDialog
        open={Boolean(candidate)}
        title="Delete document?"
        onClose={() => {
          if (!deleting) setCandidate(null);
        }}
      >
        <p>
          Delete <strong>{candidate?.title}</strong> and its searchable passages? This also removes
          related answers from this tab. This action cannot be undone.
        </p>
        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <button
            className="button secondary"
            disabled={deleting}
            onClick={() => setCandidate(null)}
          >
            Cancel
          </button>
          <button
            className="button danger"
            disabled={deleting}
            onClick={() => void confirmDelete()}
          >
            {deleting ? "Deleting…" : "Delete document"}
          </button>
        </div>
      </ModalDialog>
      <ModalDialog open={Boolean(detail)} title="Document details" onClose={() => setDetail(null)}>
        <div className="document-details">
          <h3>{detail?.title}</h3>
          <dl>
            <div>
              <dt>Filename</dt>
              <dd>{detail?.filename ?? detail?.title}</dd>
            </div>
            <div>
              <dt>File type</dt>
              <dd>PDF</dd>
            </div>
            <div>
              <dt>Pages</dt>
              <dd>{detail?.pages ?? "Not supplied"}</dd>
            </div>
            <div>
              <dt>Availability</dt>
              <dd>{detail?.isSample ? "Included sample" : "Private browser session"}</dd>
            </div>
            <div>
              <dt>Index status</dt>
              <dd>
                <span className="ready-badge">Ready</span>
              </dd>
            </div>
            <div>
              <dt>Research scope</dt>
              <dd>{detail && selectedIds.includes(detail.id) ? "Selected" : "Not selected"}</dd>
            </div>
          </dl>
        </div>
        <div className="modal-actions">
          <button className="button secondary" onClick={() => setDetail(null)}>
            Close
          </button>
        </div>
      </ModalDialog>
    </section>
  );
}
