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

export type ResearchToolCall = {
  name: string;
  arguments: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "skipped" | "failed";
  result_summary: string | null;
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

export type AnswerCitation = ResearchCitation;

export type AnswerEvidence = {
  chunk_id: string;
  document_id: string;
  page_number: number;
  text: string;
  cosine_similarity: number;
};

export type AnswerResponse = {
  answer: string;
  citations: AnswerCitation[];
  insufficient_evidence: boolean;
  degraded_mode: boolean;
  evidence: AnswerEvidence[];
};

export type ResearchJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  query: string;
  steps: ResearchStep[];
  tool_calls: ResearchToolCall[];
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

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export type DocumentSummary = {
  document_id: string;
  filename: string;
  page_count: number | null;
  is_sample: boolean;
  status: "ready";
};

function parseDocument(value: unknown): DocumentSummary {
  if (
    !isRecord(value) ||
    typeof value.document_id !== "string" ||
    typeof value.filename !== "string" ||
    (value.page_count !== null && !Number.isInteger(value.page_count)) ||
    typeof value.is_sample !== "boolean" ||
    value.status !== "ready"
  ) {
    throw new Error("The service returned an invalid document.");
  }
  return value as DocumentSummary;
}

export async function listDocuments(signal: AbortSignal): Promise<DocumentSummary[]> {
  const response = await fetch(`${API_URL}/api/v1/documents`, {
    credentials: "include",
    cache: "no-store",
    signal: AbortSignal.any([signal, AbortSignal.timeout(15_000)]),
  });
  if (!response.ok) throw await toApiError(response, "The paper library could not be loaded.");
  const payload: unknown = await response.json();
  if (!Array.isArray(payload)) throw new Error("The service returned an invalid library.");
  return payload.map(parseDocument);
}

export async function uploadDocument(file: File, signal: AbortSignal): Promise<DocumentSummary> {
  const response = await fetch(
    `${API_URL}/api/v1/documents?filename=${encodeURIComponent(file.name)}`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": file.type || "application/pdf" },
      body: file,
      signal: AbortSignal.any([signal, AbortSignal.timeout(180_000)]),
    },
  );
  if (!response.ok) throw await toApiError(response, "The PDF could not be indexed.");
  return parseDocument(await response.json());
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function isResearchToolCall(value: unknown): value is ResearchToolCall {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    isRecord(value.arguments) &&
    ["pending", "running", "completed", "skipped", "failed"].includes(String(value.status)) &&
    (value.result_summary === null || typeof value.result_summary === "string")
  );
}

function isResearchStep(value: unknown): value is ResearchStep {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    ["pending", "running", "completed", "skipped", "failed"].includes(String(value.status)) &&
    typeof value.message === "string" &&
    Number.isInteger(value.iteration) &&
    Number.isInteger(value.tool_calls_count)
  );
}

function isAnswerCitation(value: unknown): value is AnswerCitation {
  return isResearchCitation(value);
}

function isAnswerEvidence(value: unknown): value is AnswerEvidence {
  return (
    isRecord(value) &&
    typeof value.chunk_id === "string" &&
    typeof value.document_id === "string" &&
    Number.isInteger(value.page_number) &&
    typeof value.text === "string" &&
    typeof value.cosine_similarity === "number" &&
    Number.isFinite(value.cosine_similarity)
  );
}

function isResearchCitation(value: unknown): value is ResearchCitation {
  return (
    isRecord(value) &&
    typeof value.claim === "string" &&
    typeof value.chunk_id === "string" &&
    typeof value.document_id === "string" &&
    Number.isInteger(value.page_number) &&
    typeof value.quote === "string" &&
    Number.isInteger(value.quote_start) &&
    Number.isInteger(value.quote_end) &&
    Number(value.quote_start) < Number(value.quote_end)
  );
}

function isResearchSection(value: unknown): value is { heading: string; content: string } {
  return isRecord(value) && typeof value.heading === "string" && typeof value.content === "string";
}

function isResearchReport(value: unknown): value is NonNullable<ResearchJob["report"]> {
  return (
    isRecord(value) &&
    typeof value.title === "string" &&
    typeof value.summary === "string" &&
    Array.isArray(value.sections) &&
    value.sections.every(isResearchSection) &&
    Array.isArray(value.citations) &&
    value.citations.every(isResearchCitation) &&
    typeof value.partial_coverage === "boolean" &&
    (value.disclaimer === null || typeof value.disclaimer === "string")
  );
}

function isResearchEvidence(value: unknown): value is ResearchJob["evidence"][number] {
  return (
    isRecord(value) &&
    typeof value.chunk_id === "string" &&
    typeof value.document_id === "string" &&
    Number.isInteger(value.page_number) &&
    typeof value.text === "string" &&
    typeof value.cosine_similarity === "number"
  );
}

function parseResearchJob(value: unknown): ResearchJob {
  if (
    !isRecord(value) ||
    typeof value.job_id !== "string" ||
    !["queued", "running", "completed", "failed"].includes(String(value.status)) ||
    typeof value.query !== "string" ||
    !Array.isArray(value.steps) ||
    !value.steps.every(isResearchStep) ||
    !Array.isArray(value.tool_calls) ||
    !value.tool_calls.every(isResearchToolCall) ||
    typeof value.iterations !== "number" ||
    !Number.isInteger(value.iterations) ||
    value.iterations < 0 ||
    value.iterations > 4 ||
    typeof value.tool_calls_count !== "number" ||
    !Number.isInteger(value.tool_calls_count) ||
    value.tool_calls_count < 0 ||
    value.tool_calls_count > 6 ||
    !(value.sufficiency_verdict === null || typeof value.sufficiency_verdict === "boolean") ||
    !(value.report === null || isResearchReport(value.report)) ||
    !(value.error_code === null || typeof value.error_code === "string") ||
    !Array.isArray(value.evidence) ||
    !value.evidence.every(isResearchEvidence)
  )
    throw new Error("The service returned an invalid research job.");

  return {
    job_id: value.job_id,
    status: value.status as ResearchJob["status"],
    query: value.query,
    steps: value.steps,
    tool_calls: value.tool_calls,
    tool_calls_count: value.tool_calls_count,
    iterations: value.iterations,
    sufficiency_verdict: value.sufficiency_verdict,
    report: value.report,
    error_code: value.error_code,
    evidence: value.evidence,
  };
}

function parseAnswerResponse(value: unknown): AnswerResponse {
  if (
    !isRecord(value) ||
    typeof value.answer !== "string" ||
    !Array.isArray(value.citations) ||
    !value.citations.every(isAnswerCitation) ||
    typeof value.insufficient_evidence !== "boolean" ||
    typeof value.degraded_mode !== "boolean" ||
    !Array.isArray(value.evidence) ||
    !value.evidence.every(isAnswerEvidence)
  )
    throw new Error("The service returned an invalid answer.");

  return {
    answer: value.answer,
    citations: value.citations,
    insufficient_evidence: value.insufficient_evidence,
    degraded_mode: value.degraded_mode,
    evidence: value.evidence,
  };
}

async function toApiError(response: Response, fallback: string): Promise<ApiError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const detail = isRecord(payload) ? payload.detail : null;
  const message =
    typeof detail === "string"
      ? detail
      : isRecord(detail) && typeof detail.message === "string"
        ? detail.message
        : fallback;
  const explicitCode =
    isRecord(payload) && typeof payload.error_code === "string"
      ? payload.error_code
      : isRecord(detail) && typeof detail.code === "string"
        ? detail.code
        : isRecord(detail) && typeof detail.error_code === "string"
          ? detail.error_code
          : null;
  const code =
    explicitCode ??
    (typeof detail === "string" && detail.toLowerCase().includes("ocr")
      ? "OCR_NOT_SUPPORTED"
      : null);
  return new ApiError(message, response.status, code);
}

export function userFacingApiError(error: unknown): string {
  if (error instanceof DOMException && error.name === "TimeoutError")
    return "The request took too long. Try again, or ask a more focused question.";
  if (error instanceof DOMException && error.name === "AbortError")
    return "Request cancelled. You can try another question.";
  if (!(error instanceof ApiError)) {
    if (error instanceof TypeError) {
      return "Could not connect to the research service. Check the connection and try again.";
    }
    return error instanceof Error ? error.message : "The request could not be completed.";
  }
  if (error.code === "OCR_NOT_SUPPORTED") {
    return "This PDF has too little extractable text. Choose a searchable, text-based PDF; OCR is not supported.";
  }
  if (error.status === 429) {
    return "The request limit was reached. Wait a few minutes, then try again.";
  }
  if (error.status === 404) {
    return "The requested job or paper is not available in this browser session. Check the selection and try again.";
  }
  if (error.status === 413) {
    return "This PDF exceeds the upload size limit. Choose a smaller file.";
  }
  if (error.status >= 500) {
    return "The research service is temporarily unavailable. Check the connection and try again.";
  }
  return error.message || "The request could not be completed.";
}

export async function answerQuestion(
  query: string,
  documentIds: string[],
  signal?: AbortSignal,
): Promise<AnswerResponse> {
  const response = await fetch(`${API_URL}/api/v1/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    credentials: "include",
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(120_000)])
      : AbortSignal.timeout(120_000),
    body: JSON.stringify({ query, document_ids: documentIds, top_k: 5 }),
  });
  if (!response.ok) throw await toApiError(response, "The answer could not be generated.");
  return parseAnswerResponse(await response.json());
}

export async function getResearchJob(id: string, signal: AbortSignal): Promise<ResearchJob> {
  const response = await fetch(`${API_URL}/api/v1/research/${encodeURIComponent(id)}`, {
    signal,
    cache: "no-store",
    credentials: "include",
  });
  if (response.status !== 200) {
    throw await toApiError(response, "The research job could not be loaded.");
  }
  return parseResearchJob(await response.json());
}

let sessionRequest: Promise<void> | null = null;

export function ensureResearchSession(): Promise<void> {
  sessionRequest ??= startSession().finally(() => {
    sessionRequest = null;
  });
  return sessionRequest;
}

async function startSession(): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/session`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status !== 204) {
    throw await toApiError(response, "A research session could not be started.");
  }
}

export async function createResearchJob(
  query: string,
  documentIds: string[],
  signal?: AbortSignal,
): Promise<ResearchJob> {
  const response = await fetch(`${API_URL}/api/v1/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    credentials: "include",
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(30_000)])
      : AbortSignal.timeout(30_000),
    body: JSON.stringify({ query, document_ids: documentIds, top_k: 5 }),
  });
  if (response.status !== 202) {
    throw await toApiError(response, "The research request could not be started.");
  }
  return parseResearchJob(await response.json());
}

export async function getHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch(`${API_URL}/api/v1/health`, {
    signal,
    cache: "no-store",
    credentials: "include",
  });
  if (response.status !== 200 && response.status !== 503) {
    throw new Error("The service returned an unexpected response.");
  }
  const body: unknown = await response.json();
  if (
    !body ||
    typeof body !== "object" ||
    !("status" in body) ||
    !("db" in body) ||
    !("pgvector" in body) ||
    !("embedding_model" in body) ||
    !("llm_provider" in body) ||
    !("model_configured" in body) ||
    !["ready", "not_ready"].includes(String(body.status)) ||
    !["connected", "unavailable"].includes(String(body.db)) ||
    (body.pgvector !== null && typeof body.pgvector !== "string") ||
    typeof body.embedding_model !== "string" ||
    typeof body.llm_provider !== "string" ||
    typeof body.model_configured !== "boolean"
  )
    throw new Error("The service returned an invalid status response.");
  return body as Health;
}
