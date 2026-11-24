import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { answer, documents, job, jobId, mockApi } from "./fixtures";

function visibleThroughClippingAncestors(element: Element) {
  const box = element.getBoundingClientRect();
  if (!box.width || !box.height) return false;
  for (let parent = element.parentElement; parent; parent = parent.parentElement) {
    const style = getComputedStyle(parent);
    const bounds = parent.getBoundingClientRect();
    if (
      /^(auto|scroll|hidden|clip)$/.test(style.overflowY) &&
      (box.top < bounds.top || box.bottom > bounds.bottom)
    )
      return false;
    if (
      /^(auto|scroll|hidden|clip)$/.test(style.overflowX) &&
      (box.left < bounds.left || box.right > bounds.right)
    )
      return false;
  }
  return box.top >= 0 && box.bottom <= innerHeight;
}

test("a long selected quote stays visible after layout and screenshot capture", async ({
  page,
}) => {
  await mockApi(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const prefix =
    "🧪 " +
    "Educational question answering requires careful evaluation of knowledge and reasoning. ".repeat(
      50,
    );
  const quote = answer.citations[0].quote;
  const citation = {
    ...answer.citations[0],
    claim:
      answer.citations[0].claim +
      " These datasets evaluate diverse educational reasoning tasks.".repeat(8),
    quote_start: Array.from(prefix).length,
    quote_end: Array.from(prefix + quote).length,
  };
  const target = {
    ...answer.evidence[0],
    text: prefix + quote + " Further discussion of the educational evaluation.".repeat(10),
  };
  await page.route("**/api/v1/answer", (route) =>
    route.fulfill({
      json: {
        ...answer,
        answer: citation.claim,
        citations: [citation],
        evidence: [
          target,
          ...Array.from({ length: 10 }, (_, index) => ({
            ...answer.evidence[0],
            chunk_id: `follow-${index}`,
            text: "Additional educational research context.",
          })),
        ],
      },
    }),
  );
  await page.goto("/workspace");
  await page
    .getByRole("textbox", { name: "Your research question" })
    .fill("Which benchmarks are used?");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  const inline = page.locator(".markdown-content .citation-badge").first();
  await expect(inline).toBeVisible();
  await page.getByRole("button", { name: "Hide sources", exact: true }).click();
  await inline.click();
  expect
    .soft(await page.getByRole("dialog").locator("mark").evaluate(visibleThroughClippingAncestors))
    .toBe(true);
  await page.keyboard.press("Escape");
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  const mark = page.locator(".source-card.is-active mark");
  await expect(mark).toHaveText(quote);
  await page.screenshot({
    path: "../../tmp/redesign/long-source-selection-1440.png",
    fullPage: true,
  });
  expect(await mark.evaluate(visibleThroughClippingAncestors)).toBe(true);
});

test("citation selection opens and scrolls its source panel without moving the conversation", async ({
  page,
}) => {
  await mockApi(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.route("**/api/v1/answer", (route) =>
    route.fulfill({
      json: {
        ...answer,
        evidence: [
          ...Array.from({ length: 12 }, (_, index) => ({
            ...answer.evidence[0],
            chunk_id: `other-${index}`,
            text: `Background passage ${index}. Retrieved supporting context.`,
          })),
          ...answer.evidence,
        ],
      },
    }),
  );
  await page.goto("/workspace");
  await page
    .getByRole("textbox", { name: "Your research question" })
    .fill("Which benchmarks are used?");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  const inline = page.locator(".markdown-content .citation-badge").first();
  await expect(inline).toBeVisible();
  await page.getByRole("button", { name: "Hide sources", exact: true }).click();
  await expect(page.locator(".sources-panel")).toHaveCount(0);
  const position = await page.evaluate(() => scrollY);
  await inline.click();
  await page.keyboard.press("Escape");
  await expect(page.locator(".sources-panel")).toBeVisible();
  await expect(page.locator(".source-card.is-active mark")).toHaveText(answer.citations[0].quote);
  await page.locator(".source-card.is-active summary").click();
  await expect(page.locator(".source-card.is-active mark")).not.toBeVisible();
  await inline.click();
  await page.keyboard.press("Escape");
  await expect(page.locator(".source-card.is-active mark")).toBeVisible();
  expect(
    await page.locator(".sources-panel").evaluate((element) => element.scrollTop),
  ).toBeGreaterThan(0);
  expect(Math.abs((await page.evaluate(() => scrollY)) - position)).toBeLessThanOrEqual(2);
  await expect(inline).toBeFocused();
  await page.screenshot({
    path: "../../tmp/redesign/final-selected-source-1440.png",
    fullPage: true,
  });
});

test("empty composer never covers the included-paper disclosure", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/workspace");
  await expect(
    page.getByRole("button", { name: "Summarize my uploaded documents.", exact: true }),
  ).toBeEnabled();
  const disclosure = page.locator(".sample-examples summary");
  await disclosure.scrollIntoViewIfNeeded();
  expect(
    await disclosure.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return element.contains(
        document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2),
      );
    }),
  ).toBe(true);
});

test("restoring the same document set in a different order restores its answer", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/workspace");
  await page
    .getByRole("textbox", { name: "Your research question" })
    .fill("Compare the selected research");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  await expect(page.locator(".markdown-content").first()).toContainText(answer.answer);
  await page.getByRole("button", { name: /^Selected papers/ }).click();
  const first = page.getByRole("checkbox", { name: "Educational question answering", exact: true });
  await first.uncheck();
  await first.check();
  await expect(page.locator(".markdown-content").first()).toContainText(answer.answer);
});

test("header theme action in System mode follows the resolved OS appearance", async ({ page }) => {
  await mockApi(page);
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/settings");
  await page.getByRole("button", { name: "System", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const toggle = page.getByRole("button", { name: "Switch to dark theme", exact: true });
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("generated Markdown never automatically fetches remote images", async ({ page }) => {
  await mockApi(page);
  let remoteRequests = 0;
  await page.route("https://image-tracker.invalid/**", (route) => {
    remoteRequests++;
    return route.fulfill({ body: "", contentType: "image/png" });
  });
  await page.route("**/api/v1/answer", (route) =>
    route.fulfill({
      json: {
        ...answer,
        answer:
          "A sourced answer.\n\n![Illustration](https://image-tracker.invalid/pixel?private=research-content)",
        citations: [],
      },
    }),
  );
  await page.goto("/workspace");
  await page.getByRole("textbox", { name: "Your research question" }).fill("Explain this evidence");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  await expect(page.locator(".markdown-content")).toContainText("A sourced answer.");
  await expect(page.locator(".markdown-content img")).toHaveCount(0);
  expect(remoteRequests).toBe(0);
});

test("confirmed upload finishes in persistent library after route navigation", async ({ page }) => {
  await mockApi(page);
  let release!: () => void;
  const pending = new Promise<void>((resolve) => (release = resolve));
  let started = false,
    committed = false;
  const paper = {
    document_id: "navigation-upload",
    filename: "navigation-upload.pdf",
    page_count: 1,
    is_sample: false,
    status: "ready",
  };
  await page.route("**/api/v1/documents", (route) =>
    route.fulfill({ json: committed ? [...documents, paper] : documents }),
  );
  await page.route("**/api/v1/documents?filename=*", async (route) => {
    started = true;
    await pending;
    committed = true;
    await route.fulfill({ status: 201, json: paper }).catch(() => {});
  });
  await page.goto("/documents");
  await expect(page.getByRole("button", { name: "Upload documents", exact: true })).toBeEnabled();
  await page.getByLabel("Upload PDF", { exact: true }).setInputFiles({
    name: paper.filename,
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7\nfixture"),
  });
  await expect.poll(() => started).toBe(true);
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "Knowledge base", exact: true }).click();
  await expect(page).toHaveURL("/knowledge");
  release();
  await expect(page.getByRole("button", { name: paper.filename, exact: true })).toBeVisible();
});

test("confirmed deletion prunes the library and related answers after browser Back", async ({
  page,
}) => {
  await mockApi(page);
  let release!: () => void;
  const pending = new Promise<void>((resolve) => (release = resolve));
  let started = false,
    committed = false;
  const paper = {
    document_id: "navigation-delete",
    filename: "navigation-delete.pdf",
    page_count: 1,
    is_sample: false,
    status: "ready",
  };
  await page.route("**/api/v1/documents", (route) =>
    route.fulfill({ json: committed ? documents : [...documents, paper] }),
  );
  await page.route("**/api/v1/documents/navigation-delete", async (route) => {
    started = true;
    await pending;
    committed = true;
    await route.fulfill({ status: 204 }).catch(() => {});
  });
  await page.goto("/documents");
  await page.getByRole("checkbox", { name: `Select ${paper.filename}`, exact: true }).check();
  await page.getByRole("link", { name: "Workspace", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Your research question" })
    .fill("A question using the private paper");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  await expect(page.locator(".markdown-content").first()).toBeVisible();
  await page.getByRole("link", { name: "My documents", exact: true }).click();
  await page.getByRole("button", { name: `Delete ${paper.filename}`, exact: true }).click();
  await page.getByRole("button", { name: "Delete document", exact: true }).click();
  await expect.poll(() => started).toBe(true);
  await page.goBack();
  await expect(page).toHaveURL("/workspace");
  release();
  await expect(page.locator(".markdown-content")).toHaveCount(0);
  await page.getByRole("link", { name: "My documents", exact: true }).click();
  await expect(page.getByRole("button", { name: paper.filename, exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Recent conversations", exact: true }).click();
  await expect(page.locator(".conversation-row")).toHaveCount(0);
});

test("partial coverage disclaimer survives report copying and Markdown download", async ({
  page,
}) => {
  await mockApi(page);
  const complete = job(true);
  const warning = "Only part of the selected source set is covered. Verify all conclusions.";
  await page.route(`**/api/v1/research/${jobId}`, (route) =>
    route.fulfill({
      json: {
        ...complete,
        report: { ...complete.report!, partial_coverage: true, disclaimer: warning },
      },
    }),
  );
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async (text: string) => {
          document.documentElement.dataset.copiedReport = text;
        },
      },
    }),
  );
  await page.goto(`/research/${jobId}`);
  await expect(page.locator(".research-disclaimer")).toHaveText(warning);
  await page.getByRole("button", { name: "Copy report", exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.dataset.copiedReport)).toContain(
    warning,
  );
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Markdown", exact: true }).click();
  const file = await (await downloading).path();
  expect(await readFile(file!, "utf8")).toContain(warning);
});

test("four general starters preserve the selected private document scope", async ({ page }) => {
  const journal = await mockApi(page);
  const paper = {
    document_id: "scope-private",
    filename: "selected-private.pdf",
    page_count: 1,
    is_sample: false,
    status: "ready",
  };
  await page.route("**/api/v1/documents", (route) =>
    route.fulfill({ json: [...documents, paper] }),
  );
  await page.goto("/documents");
  const all = page.getByRole("checkbox", { name: "Select all displayed documents", exact: true });
  await all.check();
  await all.uncheck();
  await page.getByRole("checkbox", { name: `Select ${paper.filename}`, exact: true }).check();
  await page.getByRole("link", { name: "Workspace", exact: true }).click();
  for (const prompt of [
    "Summarize my uploaded documents.",
    "Find the key concepts across my research papers.",
    "Compare the main arguments in my documents.",
    "Find evidence supporting a particular claim.",
  ]) {
    await page.getByRole("button", { name: prompt, exact: true }).click();
    await expect(page.getByRole("textbox", { name: "Your research question" })).toHaveValue(prompt);
    expect(journal.answerBodies).toHaveLength(0);
  }
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  await expect(page.locator(".markdown-content").first()).toBeVisible();
  expect(journal.answerBodies[0].document_ids).toEqual([paper.document_id]);
});
