import http from "node:http";
import { expect, test } from "@playwright/test";

let upstream: http.Server;
test.beforeAll(async () => {
  upstream = http.createServer((request, response) => {
    if (request.url?.endsWith("/slow")) {
      setTimeout(() => {
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end('{"ok":true}');
      }, 35_000);
      return;
    }
    let received = 0;
    request.on("data", (chunk: Buffer) => {
      received += chunk.length;
    });
    request.on("end", () => {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ received }));
    });
  });
  await new Promise<void>((resolve) => upstream.listen(18005, "127.0.0.1", resolve));
});
test.afterAll(async () => {
  upstream.closeAllConnections();
  await new Promise<void>((resolve, reject) =>
    upstream.close((error) => (error ? reject(error) : resolve())),
  );
});

test("the real Next rewrite forwards a PDF larger than10MiB without truncation", async ({
  request,
}) => {
  const data = Buffer.alloc(12 * 1024 * 1024, 65);
  const response = await request.post("/api/v1/proxy-test/upload", {
    data,
    headers: { "Content-Type": "application/pdf" },
    timeout: 60_000,
  });
  expect(response.status()).toBe(200);
  expect((await response.json()).received).toBe(data.length);
});

test("the real Next rewrite permits a legitimate35-second upstream response", async ({
  request,
}) => {
  const response = await request.get("/api/v1/proxy-test/slow", { timeout: 60_000 });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ ok: true });
});
