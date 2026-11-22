export type Health = {
  status: "ready" | "not_ready";
  db: "connected" | "unavailable";
  pgvector: string | null;
  embedding_model: string;
  llm_provider: string;
  model_configured: boolean;
};

export type ResearchStep = {
  name: string;
  status: "pending" | "running" | "completed" | "skipped" | "failed";
  message: string;
  iteration: number;
  tool_calls_count: number;
};

export type ResearchCitation = {
  claim: string;
  chunk_id: string;
  document_id: string;
  page_number: number;
  quote: string;
  quote_start: number;
  quote_end: number;
};

export type ResearchJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  query: string;
  steps: ResearchStep[];
  tool_calls_count: number;
  iterations: number;
  sufficiency_verdict: boolean | null;
  report: {
    title: string;
    summary: string;
    sections: { heading: string; content: string }[];
    citations: ResearchCitation[];
    partial_coverage: boolean;
    disclaimer: string | null;
  } | null;
  error_code: string | null;
  evidence: {
    chunk_id: string;
    document_id: string;
    page_number: number;
    text: string;
    cosine_similarity: number;
  }[];
};

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function isResearchStep(value: unknown): value is ResearchStep {
  return isRecord(value) &&
    typeof value.name === "string" &&
    ["pending", "running", "completed", "skipped", "failed"].includes(String(value.status)) &&
    typeof value.message === "string" &&
    Number.isInteger(value.iteration) &&
    Number.isInteger(value.tool_calls_count);
}

function isResearchCitation(value: unknown): value is ResearchCitation {
  return isRecord(value) &&
    typeof value.claim === "string" &&
    typeof value.chunk_id === "string" &&
    typeof value.document_id === "string" &&
    Number.isInteger(value.page_number) &&
    typeof value.quote === "string" &&
    Number.isInteger(value.quote_start) &&
    Number.isInteger(value.quote_end);
}

function isResearchSection(value: unknown): value is { heading: string; content: string } {
  return isRecord(value) && typeof value.heading === "string" && typeof value.content === "string";
}

function isResearchReport(value: unknown): value is NonNullable<ResearchJob["report"]> {
  return isRecord(value) &&
    typeof value.title === "string" &&
    typeof value.summary === "string" &&
    Array.isArray(value.sections) && value.sections.every(isResearchSection) &&
    Array.isArray(value.citations) && value.citations.every(isResearchCitation) &&
    typeof value.partial_coverage === "boolean" &&
    (value.disclaimer === null || typeof value.disclaimer === "string");
}

function isResearchEvidence(value: unknown): value is ResearchJob["evidence"][number] {
  return isRecord(value) &&
    typeof value.chunk_id === "string" &&
    typeof value.document_id === "string" &&
    Number.isInteger(value.page_number) &&
    typeof value.text === "string" &&
    typeof value.cosine_similarity === "number";
}

function parseResearchJob(value: unknown): ResearchJob {
  if (
    !isRecord(value) ||
    typeof value.job_id !== "string" ||
    !["queued", "running", "completed", "failed"].includes(String(value.status)) ||
    typeof value.query !== "string" ||
    !Array.isArray(value.steps) || !value.steps.every(isResearchStep) ||
    typeof value.iterations !== "number" ||
    !Number.isInteger(value.iterations) || value.iterations < 0 || value.iterations > 4 ||
    typeof value.tool_calls_count !== "number" ||
    !Number.isInteger(value.tool_calls_count) || value.tool_calls_count < 0 || value.tool_calls_count > 6 ||
    !(value.sufficiency_verdict === null || typeof value.sufficiency_verdict === "boolean") ||
    !(value.report === null || isResearchReport(value.report)) ||
    !(value.error_code === null || typeof value.error_code === "string") ||
    !Array.isArray(value.evidence) || !value.evidence.every(isResearchEvidence)
  ) throw new Error("The service returned an invalid research job.");

  return {
    job_id: value.job_id,
    status: value.status as ResearchJob["status"],
    query: value.query,
    steps: value.steps,
    tool_calls_count: value.tool_calls_count,
    iterations: value.iterations,
    sufficiency_verdict: value.sufficiency_verdict,
    report: value.report,
    error_code: value.error_code,
    evidence: value.evidence,
  };
}

export async function getResearchJob(id: string, signal: AbortSignal): Promise<ResearchJob> {
  const response = await fetch(`${API_URL}/api/v1/research/${encodeURIComponent(id)}`, {
    signal,
    cache: "no-store",
    credentials: "include",
  });
  if (response.status !== 200) throw new Error("The research job could not be loaded.");
  return parseResearchJob(await response.json());
}

export async function ensureResearchSession(): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/session`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
  });
  if (response.status !== 204) throw new Error("A research session could not be started.");
}

export async function createResearchJob(
  query: string,
  documentIds: string[],
): Promise<ResearchJob> {
  const response = await fetch(`${API_URL}/api/v1/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    credentials: "include",
    body: JSON.stringify({ query, document_ids: documentIds, top_k: 5 }),
  });
  if (response.status === 404) {
    throw new Error("One or more documents are not visible in this browser session.");
  }
  if (response.status === 429) throw new Error("The research request limit was reached. Try later.");
  if (response.status !== 202) throw new Error("The research request could not be started.");
  return parseResearchJob(await response.json());
}

export async function getHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch(`${API_URL}/api/v1/health`, {
    signal, cache: "no-store", credentials: "include",
  });
  if (response.status !== 200 && response.status !== 503) {
    throw new Error("The service returned an unexpected response.");
  }
  const body: unknown = await response.json();
  if (
    !body || typeof body !== "object" || !("status" in body) ||
    !("db" in body) || !("pgvector" in body) ||
    !("embedding_model" in body) || !("llm_provider" in body) ||
    !("model_configured" in body) ||
    !["ready", "not_ready"].includes(String(body.status)) ||
    !["connected", "unavailable"].includes(String(body.db)) ||
    (body.pgvector !== null && typeof body.pgvector !== "string") ||
    typeof body.embedding_model !== "string" || typeof body.llm_provider !== "string" ||
    typeof body.model_configured !== "boolean"
  ) throw new Error("The service returned an invalid status response.");
  return body as Health;
}
