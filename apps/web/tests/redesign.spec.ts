import { expect, test } from "@playwright/test";
import {
  answer,
  citation,
  documents,
  ids,
  job,
  jobId,
  mockApi,
  selectIncludedExample,
} from "./fixtures";
import { readFile } from "node:fs/promises";

test("public product page works independently of the API", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/")) apiRequests.push(request.url());
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Turn your documents into intelligent answers." }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Start researching", exact: true })).toHaveAttribute(
    "href",
    "/workspace",
  );
  await expect(page.getByRole("heading", { name: "From documents to discovery." })).toBeVisible();
  expect(apiRequests).toEqual([]);
});

test("starter only fills the composer and Enter explicitly submits once", async ({ page }) => {
  const journal = await mockApi(page);
  await page.goto("/workspace");
  await expect(
    page.getByRole("button", { name: "Summarize my uploaded documents.", exact: true }),
  ).toBeEnabled();
  await expect(page.getByRole("button", { name: "Ask papers", exact: true })).toBeDisabled();
  await page.getByRole("textbox", { name: "Your research question" }).fill("   ");
  await expect(page.getByRole("button", { name: "Ask papers", exact: true })).toBeDisabled();
  await selectIncludedExample(page, "Educational QA benchmarks");
  const input = page.getByRole("textbox", { name: "Your research question" });
  await expect(input).toHaveValue(
    "Which five benchmarks are used to evaluate the educational question-answering system?",
  );
  expect(journal.answerBodies).toHaveLength(0);
  await input.press("Enter");
  await expect(page.locator(".markdown-content").first()).toContainText(answer.answer);
  expect(journal.answerBodies).toHaveLength(1);
  expect(journal.answerBodies[0].document_ids).toEqual([ids[0]]);
});

test("sidebar collapses and mobile navigation is keyboard accessible", async ({ page }) => {
  await mockApi(page);
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.locator(".app-shell")).toHaveClass(/is-collapsed/);
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  const navigation = page.getByRole("dialog", { name: "Workspace navigation" });
  await expect(navigation).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(navigation).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeFocused();
});

test("saved answers are actual tab activity and never browser-persisted", async ({ page }) => {
  await mockApi(page);
  await page.goto("/workspace");
  await page
    .getByRole("textbox", { name: "Your research question" })
    .fill("Which benchmarks are used?");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  await expect(page.locator(".markdown-content").first()).toContainText(answer.answer);
  await page.getByRole("button", { name: "Save answer", exact: true }).click();
  await page.getByRole("link", { name: "Saved research", exact: true }).click();
  await expect(page).toHaveURL("/saved");
  await expect(
    page.locator(".conversation-row").getByText("Which benchmarks are used?", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage })),
  ).not.toContain("AI2_ARC");
  await page.reload();
  await expect(page.getByText("No saved research in this tab.", { exact: true })).toBeVisible();
});

test("document search and confirmed deletion use the ownership API", async ({ page }) => {
  await mockApi(page);
  const paper = {
    document_id: "private-paper",
    filename: "my-study.pdf",
    page_count: 4,
    is_sample: false,
    status: "ready",
  };
  let removed = false;
  const deletes: string[] = [];
  await page.route("**/api/v1/documents", (route) =>
    route.fulfill({ json: removed ? documents : [...documents, paper] }),
  );
  await page.route("**/api/v1/documents/private-paper", async (route) => {
    deletes.push(route.request().method());
    removed = true;
    await route.fulfill({ status: 204 });
  });
  await page.goto("/documents");
  await page.getByRole("searchbox", { name: "Search documents" }).fill("my-study");
  await expect(page.getByText("my-study.pdf", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Delete my-study.pdf" }).click();
  expect(deletes).toHaveLength(0);
  await page.getByRole("dialog").getByRole("button", { name: "Cancel", exact: true }).click();
  expect(deletes).toHaveLength(0);
  await page.getByRole("button", { name: "Delete my-study.pdf" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete document", exact: true })
    .click();
  await expect(page.getByText("my-study.pdf", { exact: true })).toHaveCount(0);
  expect(deletes).toEqual(["DELETE"]);
});

test("appearance preferences work without pretending there is account authentication", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/settings");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Light", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByText("Private browser session", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("textbox", { name: /password/i })).toHaveCount(0);
});

test("inline references are compact and still open the exact source", async ({ page }) => {
  await mockApi(page);
  await page.goto("/workspace");
  await page
    .getByRole("textbox", { name: "Your research question" })
    .fill("Which benchmarks are used?");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  const reference = page
    .locator(".markdown-content")
    .getByRole("button", { name: "Open Educational QA, page 7", exact: true });
  await expect(reference).toHaveText("[1]");
  await reference.click();
  await expect(page.getByRole("dialog").locator("mark")).toHaveText(citation.quote);
});

test("public mobile navigation closes with Escape from its trigger", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Mobile public navigation" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("navigation", { name: "Mobile public navigation" }),
  ).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Open navigation", exact: true })).toBeFocused();
});

test("light secondary controls keep readable text contrast", async ({ page }) => {
  await mockApi(page);
  await page.goto("/settings");
  await page.getByRole("button", { name: "Light", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const contrast = await page
    .getByRole("button", { name: "Use compact navigation", exact: true })
    .evaluate((element) => {
      const style = getComputedStyle(element);
      const luminance = (color: string) => {
        const rgb = color
          .match(/[\d.]+/g)!
          .slice(0, 3)
          .map((n) => Number(n) / 255)
          .map((n) => (n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4));
        return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
      };
      const a = luminance(style.color),
        b = luminance(style.backgroundColor);
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    });
  expect(contrast).toBeGreaterThanOrEqual(4.5);
});

test("browse files opens the real file chooser and indexes the selected PDF", async ({ page }) => {
  const journal = await mockApi(page);
  await page.goto("/documents");
  await page.getByRole("button", { name: "Upload documents", exact: true }).click();
  const choosing = page.waitForEvent("filechooser");
  await page.getByRole("dialog").getByRole("button", { name: "Browse files", exact: true }).click();
  const chooser = await choosing;
  await chooser.setFiles({
    name: "my-paper.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-mock"),
  });
  await expect(
    page.locator(".document-row").getByText("my-paper.pdf", { exact: true }),
  ).toBeVisible();
  expect(journal.uploads).toBe(1);
});

test("mobile sources control opens a usable source selector", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Sources", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Select sources" });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("checkbox", { name: "Educational question answering", exact: true }),
  ).toBeVisible();
});

test("Markdown export includes the actual cited source passages", async ({ page }) => {
  await mockApi(page);
  await page.route(`**/api/v1/research/${jobId}`, (route) => route.fulfill({ json: job(true) }));
  await page.goto(`/research/${jobId}`);
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Markdown", exact: true }).click();
  const download = await downloading;
  const file = await download.path();
  expect(file).not.toBeNull();
  const content = await readFile(file!, "utf8");
  expect(content).toContain("## Sources");
  expect(content).toContain(citation.quote);
  expect(content).toContain("Page 7");
});

test("deleting an unrelated private document preserves the active answer", async ({ page }) => {
  await mockApi(page);
  const privatePaper = {
    document_id: "unused-private",
    filename: "unused.pdf",
    page_count: 1,
    is_sample: false,
    status: "ready",
  };
  await page.route("**/api/v1/documents", (route) =>
    route.fulfill({ json: [...documents, privatePaper] }),
  );
  await page.route("**/api/v1/documents/unused-private", (route) => route.fulfill({ status: 204 }));
  await page.goto("/workspace");
  await page
    .getByRole("textbox", { name: "Your research question" })
    .fill("Which benchmarks are used?");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  await expect(page.locator(".markdown-content").first()).toContainText(answer.answer);
  await page.getByRole("link", { name: "My documents", exact: true }).click();
  await expect(page).toHaveURL("/documents");
  await page.getByRole("button", { name: "Delete unused.pdf", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete document", exact: true })
    .click();
  await expect(page.getByRole("dialog", { name: "Delete document?" })).not.toBeVisible();
  await page.getByRole("link", { name: "Workspace", exact: true }).click();
  await expect(page).toHaveURL("/workspace");
  await expect(page.locator(".markdown-content").first()).toContainText(answer.answer);
});

test("insufficient answers are never described as cited in history", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/v1/answer", (route) =>
    route.fulfill({
      json: {
        ...answer,
        answer: "No supporting evidence was found.",
        citations: [],
        insufficient_evidence: true,
      },
    }),
  );
  await page.goto("/workspace");
  await page.getByRole("textbox", { name: "Your research question" }).fill("An unrelated question");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  await expect(page.locator(".markdown-content").first()).toContainText("No supporting evidence");
  await page.getByRole("link", { name: "Recent conversations", exact: true }).click();
  await expect(page).toHaveURL("/history");
  await expect(page.locator(".conversation-row")).toContainText("Insufficient evidence");
});

test("rate-limit feedback uses the actual Retry-After wait", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/v1/answer", (route) =>
    route.fulfill({
      status: 429,
      headers: { "Retry-After": "42" },
      json: { detail: "Rate limit reached." },
    }),
  );
  await page.goto("/workspace");
  await page.getByRole("textbox", { name: "Your research question" }).fill("A question");
  await page.getByRole("button", { name: "Ask papers", exact: true }).click();
  await expect(page.locator('.notice[role="alert"]')).toContainText("42 seconds");
});

for (const width of [1440, 1280, 1024, 768, 390, 360]) {
  test(`redesigned routes fit ${width}px with reduced motion`, async ({ page }) => {
    await mockApi(page);
    await page.setViewportSize({ width, height: 960 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    for (const route of [
      "/",
      "/workspace",
      "/documents",
      "/knowledge",
      "/history",
      "/saved",
      "/settings",
      "/about",
    ]) {
      await page.goto(route);
      await expect(page.locator("h1").first()).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      if ([1440, 390, 360].includes(width) || route === "/workspace") {
        await page.evaluate(() => document.fonts.ready);
        await page.screenshot({
          path: `../../tmp/redesign/final-${width}-${route.slice(1) || "landing"}.png`,
          fullPage: true,
        });
      }
    }
    expect(errors).toEqual([]);
  });
}
