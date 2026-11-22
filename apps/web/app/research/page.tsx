"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createResearchJob, ensureResearchSession } from "@/lib/api";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function ResearchStartPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [documents, setDocuments] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const documentIds = documents.split(/[\s,]+/).filter(Boolean);
    if (documentIds.length < 2 || documentIds.length > 10 || documentIds.some((id) => !UUID_PATTERN.test(id))) {
      setError("Enter 2–10 valid document IDs, separated by commas or new lines.");
      return;
    }
    if (new Set(documentIds).size !== documentIds.length) {
      setError("Each document ID must be unique.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await ensureResearchSession();
      const job = await createResearchJob(query, documentIds);
      router.push(`/research/${job.job_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The request could not be started.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="document-page research-start">
      <p className="section-label">Multi-document research</p>
      <h1>Bring sources into conversation.</h1>
      <p className="lede">Ask a question across ready sample papers or documents owned by this browser session.</p>
      <form className="research-form" onSubmit={(event) => void submit(event)}>
        <label htmlFor="research-query">Research question</label>
        <textarea
          id="research-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          maxLength={4000}
          required
          rows={4}
          placeholder="For example: Which five benchmarks are used to evaluate the educational question-answering system?"
        />
        <label htmlFor="research-documents">Document IDs</label>
        <textarea
          id="research-documents"
          value={documents}
          onChange={(event) => setDocuments(event.target.value)}
          required
          rows={3}
          placeholder="Paste 2–10 document IDs, separated by commas or new lines"
        />
        <p className="research-form-note">Only ready sample documents and unexpired documents owned by this session are available.</p>
        {error && <p className="research-error" role="alert">{error}</p>}
        <button className="button" type="submit" disabled={submitting}>
          {submitting ? "Starting research…" : "Start research"}
        </button>
      </form>
    </section>
  );
}
