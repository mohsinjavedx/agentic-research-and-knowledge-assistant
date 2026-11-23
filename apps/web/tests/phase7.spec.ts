import { expect, test } from "@playwright/test";
import { citation, documents, health, ids, job, jobId, mockApi } from "./fixtures";

test("first visitor asks, inspects an inline Unicode citation, then completes a comparison", async ({
  page,
}) => {
  const journal = await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Educational QA benchmarks" })).toBeEnabled();
  await page.screenshot({ path: "test-results/workspace-1280.png", fullPage: true });
  await page.getByRole("button", { name: "Educational QA benchmarks" }).click();
  await expect(page.locator(".markdown-content").first()).toContainText(citation.claim);
  expect(journal.answerBodies[0]).toMatchObject({
    document_ids: [ids[0]],
    query: "Which five benchmarks are used to evaluate the educational question-answering system?",
  });
  const inline = page
    .locator(".markdown-content")
    .getByRole("button", { name: "Open Educational QA, page 7" });
  await inline.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator("mark")).toHaveText(citation.quote);
  await expect(dialog.getByText("0.912", { exact: true })).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(inline).toBeFocused();
  await page.getByRole("button", { name: "Compare the three papers" }).click();
  await expect(page).toHaveURL(`/research/${jobId}`);
  await expect(
    page.getByRole("heading", { name: "Evaluation across three papers", exact: true }).first(),
  ).toBeVisible();
  expect(journal.researchBodies[0].document_ids).toEqual(ids);
  expect(journal.polls).toBeGreaterThanOrEqual(2);
  await expect(page.getByRole("heading", { name: "Tool calls", exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Evidence collected", exact: true }),
  ).toBeVisible();
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0);
  await page.screenshot({ path: "test-results/research-complete-1280.png", fullPage: true });
});

test("a mismatched source range never receives an invented highlight", async ({ page }) => {
  await mockApi(page, { invalidQuote: true });
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Educational QA benchmarks" }).click();
  await page.getByRole("button", { name: "Open Educational QA, page 7" }).first().click();
  await expect(page.getByRole("dialog").locator("mark")).toHaveCount(0);
  await expect(page.getByRole("dialog").getByText(/exact highlight unavailable/i)).toBeVisible();
});

test("quota errors release the composer and explain how to retry", async ({ page }) => {
  await mockApi(page, { quota: true });
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Educational QA benchmarks" }).click();
  await expect(page.locator('.notice[role="alert"]')).toContainText("request limit");
  await expect(page.getByRole("button", { name: "Ask papers", exact: true })).toBeEnabled();
});

test("sleeping backend shows a delayed banner then unlocks the composer", async ({ page }) => {
  await mockApi(page);
  let release: (() => void) | undefined;
  await page.route("**/api/v1/health", async (route) => {
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    await route.fulfill({ json: health });
  });
  await page.clock.install();
  await page.goto("/workspace");
  await expect(page.getByRole("button", { name: "Ask papers", exact: true })).toBeDisabled();
  await page.clock.fastForward(3100);
  await expect(page.getByText(/waking up/i).first()).toBeVisible();
  release?.();
  await expect(page.getByRole("button", { name: "Ask papers", exact: true })).toBeEnabled();
});

test("unresponsive health terminates and offers retry", async ({ page }) => {
  await mockApi(page);
  let healthRequested = false;
  await page.route("**/api/v1/health", () => {
    healthRequested = true;
    return new Promise(() => {});
  });
  await page.clock.install();
  await page.goto("/workspace");
  await expect(page.getByRole("button", { name: "Ask papers", exact: true })).toBeDisabled();
  await expect.poll(() => healthRequested).toBe(true);
  await page.clock.fastForward(60_100);
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeVisible();
  await expect(page.getByText(/longer than expected/i)).toBeVisible();
});

test("OCR upload errors are actionable and leave upload available", async ({ page }) => {
  const journal = await mockApi(page, { ocr: true });
  await page.goto("/documents");
  await expect(page.getByLabel("Upload PDF")).toBeEnabled();
  await page.getByLabel("Upload PDF").setInputFiles({
    name: "scanned.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-mocked-scan"),
  });
  await expect(page.locator('.notice[role="alert"]')).toContainText("OCR is not supported");
  await expect(page.getByLabel("Upload PDF")).toBeEnabled();
  expect(journal.uploads).toBe(1);
});

test("uploaded paper is added to the private library", async ({ page }) => {
  await mockApi(page);
  await page.goto("/documents");
  await expect(page.getByLabel("Upload PDF")).toBeEnabled();
  await page.getByLabel("Upload PDF").setInputFiles({
    name: "my-paper.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-mocked-text"),
  });
  await expect(page.getByText("my-paper.pdf", { exact: true }).first()).toBeVisible();
  await page.getByRole("link", { name: "Workspace", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: /my-paper.pdf/ })).toBeChecked();
});

test("an older library response cannot discard a newly uploaded paper", async ({ page }) => {
  await mockApi(page);
  let release: (() => void) | undefined;
  let delayed = false;
  await page.route("**/api/v1/documents", async (route) => {
    if (route.request().method() !== "GET" || delayed) return route.fallback();
    delayed = true;
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    await route.fulfill({ json: documents });
  });
  await page.goto("/documents");
  await expect(page.getByLabel("Upload PDF")).toBeEnabled();
  await expect.poll(() => !!release).toBe(true);
  await page.getByLabel("Upload PDF").setInputFiles({
    name: "my-paper.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-mock"),
  });
  await expect(page.getByText("my-paper.pdf", { exact: true })).toBeVisible();
  const response = page.waitForResponse(
    (result) => result.url().endsWith("/api/v1/documents") && result.request().method() === "GET",
  );
  release?.();
  await response;
  await page.getByRole("link", { name: "Workspace", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "my-paper.pdf", exact: true })).toBeChecked();
});

test("an answer request deadline releases the controls with a retryable message", async ({
  page,
}) => {
  await page.addInitScript(() => {
    AbortSignal.timeout = (milliseconds: number) => {
      const controller = new AbortController();
      setTimeout(
        () => controller.abort(new DOMException("Timed out", "TimeoutError")),
        milliseconds,
      );
      return controller.signal;
    };
  });
  await page.clock.install();
  await mockApi(page);
  await page.route("**/api/v1/answer", () => new Promise(() => {}));
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Educational QA benchmarks" }).click();
  await expect(page.getByRole("button", { name: "Cancel", exact: true })).toBeVisible();
  await page.clock.fastForward(120_100);
  await expect(page.locator('.notice[role="alert"]')).toContainText("took too long");
  await expect(page.getByRole("button", { name: "Ask papers", exact: true })).toBeEnabled();
});

test("a stalled research run stops polling after its waiting budget", async ({ page }) => {
  await mockApi(page);
  await page.route(`**/api/v1/research/${jobId}`, (route) => route.fulfill({ json: job(false) }));
  await page.clock.install();
  await page.goto(`/research/${jobId}`);
  await expect(page.getByText("Research in progress", { exact: true })).toBeVisible();
  await page.clock.fastForward(600_100);
  await expect(page.locator('.notice[role="alert"]')).toContainText("longer than expected");
  await expect(page.getByRole("button", { name: "Retry job status" })).toBeVisible();
});

test("private citations keep filenames and reset their copy status", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await mockApi(page);
  const privatePapers = ["first-study.pdf", "second-study.pdf"].map((filename, index) => ({
    document_id: `private-${index}`,
    filename,
    page_count: 2,
    is_sample: false,
    status: "ready",
  }));
  await page.route("**/api/v1/documents", (route) =>
    route.fulfill({ json: [...documents, ...privatePapers] }),
  );
  const citations = privatePapers.map((paper, index) => ({
    ...citation,
    document_id: paper.document_id,
    chunk_id: `private-chunk-${index}`,
    page_number: 1,
    claim: `Paper ${index + 1} describes its findings.`,
    quote: `Paper ${index + 1} describes its findings.`,
    quote_start: 0,
    quote_end: 31,
  }));
  const evidence = citations.map((source) => ({
    ...source,
    text: source.quote,
    cosine_similarity: 0.8,
  }));
  await page.route("**/api/v1/answer", (route) =>
    route.fulfill({
      json: {
        answer: citations.map((source) => source.claim).join(" "),
        citations,
        evidence,
        insufficient_evidence: false,
        degraded_mode: false,
      },
    }),
  );
  await page.goto("/workspace");
  await expect(page.getByRole("checkbox", { name: "first-study.pdf", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Educational QA benchmarks" }).click();
  const inline = page.locator(".markdown-content");
  await inline.getByRole("button", { name: "Open first-study.pdf, page 1" }).click();
  await expect(
    page.getByRole("dialog").getByText("first-study.pdf", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Copy quote", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copied", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await inline.getByRole("button", { name: "Open second-study.pdf, page 1" }).click();
  await expect(
    page.getByRole("dialog").getByText("second-study.pdf", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy quote", exact: true })).toBeVisible();
});

for (const width of [360, 768, 1280]) {
  test(`all routes and source drawer fit ${width}px, including reduced motion`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mockApi(page);
    for (const path of ["/", "/workspace", "/documents", `/research/${jobId}`]) {
      await page.goto(path);
      await expect(page.locator("h1").first()).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
    }
    await page.goto("/workspace");
    await page.getByRole("button", { name: "Educational QA benchmarks" }).click();
    await page.getByRole("button", { name: "Open Educational QA, page 7" }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("dialog").locator("mark")).toHaveText(citation.quote);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: `test-results/source-${width}.png` });
  });
}
