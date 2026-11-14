export type Health = {
  status: "ready" | "not_ready";
  db: "connected" | "unavailable";
  pgvector: string | null;
  embedding_model: string;
  llm_provider: string;
  model_configured: boolean;
};

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

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
