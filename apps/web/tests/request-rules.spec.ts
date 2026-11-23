import { expect, test } from "@playwright/test";
import { selectionError } from "../lib/request-rules";

test("answer scope admits50 documents and explains the extra selection", () => {
  expect(selectionError(50, "answer")).toBeNull();
  expect(selectionError(51, "answer")).toContain("Deselect 1 paper");
  expect(selectionError(0, "answer")).toContain("at least one");
});

test("research scope admits10 documents and requires two", () => {
  expect(selectionError(10, "research")).toBeNull();
  expect(selectionError(11, "research")).toContain("Deselect 1 paper");
  expect(selectionError(1, "research")).toContain("at least two");
});
