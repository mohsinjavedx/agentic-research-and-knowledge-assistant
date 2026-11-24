import type { Page } from "@playwright/test";

export async function selectIncludedExample(page: Page, name: string) {
  const button = page.getByRole("button", { name, exact: true });
  if (!(await button.isVisible()))
    await page.getByText("Included-paper examples", { exact: true }).click();
  await button.click();
}

export const ids = [
  "35d86749-bf13-55ac-8008-231937b43bab",
  "a0fba681-ef99-5f3b-aee3-91ea98269e33",
  "be12ca47-9e95-56c9-abdc-104a9f7680f5",
];
export const jobId = "00000000-0000-4000-8000-000000000007";
export const health = {
  status: "ready",
  db: "connected",
  pgvector: "0.8.2",
  embedding_model: "BAAI/bge-small-en-v1.5",
  llm_provider: "hosted",
  model_configured: true,
};
const quote = "AI2_ARC, OpenBookQA, E-EVAL, Textbook Question Answering (TQA), and ScienceQA.";
const prefix = "🧪 Source note.\n\n";
export const citation = {
  claim: `The five benchmarks are ${quote}`,
  chunk_id: "chunk-7",
  document_id: ids[0],
  page_number: 7,
  quote,
  quote_start: Array.from(prefix).length,
  quote_end: Array.from(prefix + quote).length,
};
export const evidence = [
  {
    chunk_id: "chunk-7",
    document_id: ids[0],
    page_number: 7,
    text: prefix + quote + "\n\nEach evaluates educational question answering.",
    cosine_similarity: 0.912,
  },
];
export const answer = {
  answer: citation.claim,
  citations: [citation],
  insufficient_evidence: false,
  degraded_mode: false,
  evidence,
};
export const documents = ids.map((id, i) => ({
  document_id: id,
  filename: ["education.pdf", "nutrition.pdf", "medical.pdf"][i],
  page_count: 20,
  is_sample: true,
  status: "ready",
}));
export function job(completed: boolean) {
  return {
    job_id: jobId,
    status: completed ? "completed" : "running",
    query: "Compare the evaluation approaches described in these papers.",
    iterations: 1,
    tool_calls_count: 1,
    sufficiency_verdict: completed ? true : null,
    steps: [
      {
        name: "plan",
        status: "completed",
        message: "Compare the evaluation approaches of the three papers.",
        iteration: 1,
        tool_calls_count: 0,
      },
      {
        name: "retrieve",
        status: completed ? "completed" : "running",
        message: "Collecting evidence from the selected papers.",
        iteration: 1,
        tool_calls_count: 1,
      },
    ],
    tool_calls: [
      {
        name: "search_documents",
        arguments: { query: "evaluation approaches", document_ids: ids },
        status: "completed",
        result_summary: "Retrieved the comparison evidence.",
      },
    ],
    evidence,
    error_code: null,
    report: completed
      ? {
          title: "Evaluation across three papers",
          summary: citation.claim,
          sections: [
            {
              heading: "Comparison",
              content: "The papers evaluate different tasks.\n\n[Unsafe link](javascript:alert(1))",
            },
          ],
          citations: [citation],
          partial_coverage: false,
          disclaimer: null,
        }
      : null,
  };
}

export async function mockApi(
  page: Page,
  options: { quota?: boolean; ocr?: boolean; invalidQuote?: boolean } = {},
) {
  const journal = {
    answerBodies: [] as Record<string, unknown>[],
    researchBodies: [] as Record<string, unknown>[],
    polls: 0,
    uploads: 0,
  };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (request.method() === "OPTIONS")
      return route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "http://127.0.0.1:3000",
          "Access-Control-Allow-Credentials": "true",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    const headers = {
      "Access-Control-Allow-Origin": "http://127.0.0.1:3000",
      "Access-Control-Allow-Credentials": "true",
    };
    if (pathname.endsWith("/health")) return route.fulfill({ json: health, headers });
    if (pathname.endsWith("/session")) return route.fulfill({ status: 204, headers });
    if (pathname.endsWith("/documents")) {
      if (request.method() === "GET") return route.fulfill({ json: documents, headers });
      journal.uploads++;
      if (options.ocr)
        return route.fulfill({
          status: 422,
          json: { detail: { code: "OCR_NOT_SUPPORTED", message: "Choose a text-based PDF." } },
          headers,
        });
      return route.fulfill({
        status: 201,
        json: {
          document_id: "00000000-0000-4000-8000-000000000099",
          filename: "my-paper.pdf",
          page_count: 2,
          is_sample: false,
          status: "ready",
        },
        headers,
      });
    }
    if (pathname.endsWith("/answer")) {
      journal.answerBodies.push(request.postDataJSON());
      if (options.quota)
        return route.fulfill({ status: 429, json: { detail: "Quota exceeded" }, headers });
      return route.fulfill({
        json: options.invalidQuote
          ? { ...answer, citations: [{ ...citation, quote_end: citation.quote_end - 1 }] }
          : answer,
        headers,
      });
    }
    if (pathname.endsWith("/research")) {
      journal.researchBodies.push(request.postDataJSON());
      return route.fulfill({ status: 202, json: { ...job(false), status: "queued" }, headers });
    }
    if (pathname.endsWith(`/research/${jobId}`)) {
      journal.polls++;
      return route.fulfill({ json: job(journal.polls > 1), headers });
    }
    return route.fulfill({ status: 404, json: { detail: "Not found" }, headers });
  });
  return journal;
}
