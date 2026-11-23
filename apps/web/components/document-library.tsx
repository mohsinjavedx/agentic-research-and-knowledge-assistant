"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  CheckCircle,
  FilePdf,
  ShieldCheck,
  UploadSimple,
} from "@phosphor-icons/react";
import { useBackendReadiness } from "@/components/backend-readiness";
import { useSourceLibrary } from "@/components/source-library";
import { ensureResearchSession, uploadDocument, userFacingApiError } from "@/lib/api";

export function DocumentLibrary() {
  const { isReady } = useBackendReadiness();
  const {
    documents,
    selectedIds,
    setSelectedIds,
    addDocument,
    error: libraryError,
    refresh,
  } = useSourceLibrary();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [dragging, setDragging] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function upload(file: File | undefined) {
    if (!file || busy || !isReady) return;
    setError("");
    setSuccess("");
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Choose a PDF file. Other file formats are not supported.");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError("This PDF exceeds 20 MiB. Choose a smaller file.");
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    try {
      await ensureResearchSession();
      if (controller.signal.aborted) return;
      const result = await uploadDocument(file, controller.signal);
      if (controller.signal.aborted) return;
      addDocument(result);
      setSuccess(`${result.filename} is ready to explore.`);
    } catch (reason) {
      if (!controller.signal.aborted) setError(userFacingApiError(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="library-page page-enter">
      <header className="page-heading">
        <div>
          <span className="context-label">
            <FilePdf size={17} />
            Your reading collection
          </span>
          <h1>
            A home for your
            <br />
            next discovery.
          </h1>
          <p className="lede">Bring your papers together. Keep every answer close to its source.</p>
        </div>
        <Link className="button secondary" href="/workspace">
          Open workspace
          <ArrowUpRight size={17} />
        </Link>
      </header>
      <div
        className={`upload-zone${dragging ? " is-dragging" : ""}${busy ? " is-working" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (isReady && !busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void upload(event.dataTransfer.files[0]);
        }}
      >
        <span className="upload-symbol">
          <UploadSimple size={28} />
        </span>
        <div>
          <h2>{busy ? "Preparing your paper…" : "Make room for another perspective"}</h2>
          <p>
            {busy
              ? "Validating the PDF, reading its pages, and indexing its sources."
              : "Drop a searchable PDF here, or choose one from your device."}
          </p>
          <span className="file-limits">
            PDF only · Up to 20 MiB · 100 pages · No scanned images
          </span>
        </div>
        <label className={`button upload-button${!isReady || busy ? " disabled" : ""}`}>
          Choose PDF
          <input
            className="upload-input"
            type="file"
            accept="application/pdf,.pdf"
            aria-label="Upload PDF"
            disabled={!isReady || busy}
            onChange={(event) => {
              void upload(event.currentTarget.files?.[0]);
              event.currentTarget.value = "";
            }}
          />
        </label>
        {busy && (
          <div className="upload-progress" role="status" aria-label="Indexing PDF">
            <span />
          </div>
        )}
      </div>
      {error && (
        <div className="notice error" role="alert">
          <strong>We couldn’t add that paper.</strong>
          <p>{error}</p>
        </div>
      )}
      {success && (
        <p className="notice success" role="status">
          <CheckCircle size={18} />
          {success}
        </p>
      )}
      {libraryError && (
        <div className="notice">
          <p>{libraryError}</p>
          <button className="text-button" onClick={refresh}>
            Retry library
          </button>
        </div>
      )}
      <div className="library-heading">
        <h2>
          Your papers <span className="count-badge">{documents.length}</span>
        </h2>
        <span>
          <ShieldCheck size={15} />
          Private uploads expire after 24 hours
        </span>
      </div>
      <div className="document-grid">
        {documents.map((paper, index) => (
          <article
            className={`document-card${selectedIds.includes(paper.id) ? " selected" : ""}`}
            key={paper.id}
          >
            <div className={`document-cover paper-color-${index % 3}`}>
              <FilePdf size={38} weight="duotone" />
              <span>{paper.isSample ? "Research paper" : "Your PDF"}</span>
              <div className="paper-lines" aria-hidden="true">
                <i />
                <i />
                <i />
              </div>
            </div>
            <div className="document-card-body">
              <span className="paper-type">
                {paper.isSample ? "Included sample" : "Private upload"}
                {paper.pages ? ` · ${paper.pages} pages` : ""}
              </span>
              <h3>{paper.title}</h3>
              <p>{paper.detail}</p>
              <label className="library-selection">
                <input
                  type="checkbox"
                  aria-label={`Select ${paper.title}`}
                  checked={selectedIds.includes(paper.id)}
                  onChange={() =>
                    setSelectedIds((current) =>
                      current.includes(paper.id)
                        ? current.filter((id) => id !== paper.id)
                        : [...current, paper.id],
                    )
                  }
                />
                <span>
                  {selectedIds.includes(paper.id) ? "Selected in workspace" : "Select for research"}
                </span>
              </label>
            </div>
          </article>
        ))}
      </div>
      {!documents.length && !libraryError && (
        <div className="empty-state">
          <BooksPlaceholder />
          <h2>Your next idea starts with a paper.</h2>
          <p>Add a searchable PDF to begin asking questions.</p>
        </div>
      )}
    </section>
  );
}

function BooksPlaceholder() {
  return <FilePdf size={38} weight="duotone" />;
}
