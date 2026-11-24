"use client";

import { useRef, useState } from "react";
import { FileUp, ShieldCheck, Upload } from "lucide-react";
import { ModalDialog } from "@/components/modal-dialog";
import { useBackendReadiness } from "@/components/backend-readiness";
import { useSourceLibrary } from "@/components/source-library";
import { userFacingApiError } from "@/lib/api";

export function DocumentUpload({
  onSuccess,
  open,
  onOpenChange: setOpen,
}: {
  onSuccess: (message: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { isReady } = useBackendReadiness();
  const { uploadFile, uploading: busy } = useSourceLibrary();
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  async function upload(file: File | undefined) {
    if (!file || busy || !isReady) return;
    setOpen(true);
    setError("");
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Choose a PDF file. Other file formats are not supported.");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError("This PDF exceeds 20 MiB. Choose a smaller file.");
      return;
    }
    try {
      const result = await uploadFile(file);
      onSuccess(`${result.filename} is ready to explore.`);
      setOpen(false);
    } catch (reason) {
      setError(userFacingApiError(reason));
    }
  }
  return (
    <>
      <input
        ref={input}
        className="upload-input"
        type="file"
        tabIndex={-1}
        accept="application/pdf,.pdf"
        aria-label="Upload PDF"
        disabled={!isReady || busy}
        onChange={(event) => {
          void upload(event.currentTarget.files?.[0]);
          event.currentTarget.value = "";
        }}
      />
      <button className="button" disabled={!isReady} onClick={() => setOpen(true)}>
        <Upload size={16} />
        {busy ? "Indexing PDF…" : "Upload documents"}
      </button>
      {busy && !open && (
        <span className="sr-only" role="status">
          Your PDF is being uploaded and indexed.
        </span>
      )}
      <ModalDialog open={open} title="Upload documents" onClose={() => setOpen(false)}>
        <div
          className={`upload-zone${dragging ? " is-dragging" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            if (isReady && !busy) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            if (event.dataTransfer.files.length > 1) {
              setError("Upload one PDF at a time.");
              return;
            }
            void upload(event.dataTransfer.files[0]);
          }}
        >
          <span className="upload-symbol">
            {busy ? <span className="activity-indicator" /> : <FileUp size={24} />}
          </span>
          <h3>{busy ? "Preparing your paper…" : "Drag and drop your documents here"}</h3>
          <p>
            {busy
              ? "Uploading, validating, extracting text, and building searchable embeddings."
              : "Bring a paper you want to understand better."}
          </p>
          {!busy && (
            <button
              className="button secondary"
              disabled={!isReady}
              onClick={() => input.current?.click()}
            >
              Browse files
            </button>
          )}
          <span className="file-limits">
            Text-based PDF · Up to 20 MiB · 100 pages · One file at a time
          </span>
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
        <p className="upload-privacy">
          <ShieldCheck size={15} />
          <span>
            Uploads are private to this browser session. A paper appears as ready only after
            indexing succeeds. Scanned PDFs require OCR, which is not supported.
          </span>
        </p>
      </ModalDialog>
    </>
  );
}
