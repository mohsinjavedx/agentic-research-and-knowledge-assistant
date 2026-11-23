export function selectionError(count: number, mode: "answer" | "research"): string | null {
  if (count < (mode === "research" ? 2 : 1)) {
    return mode === "research"
      ? "Select at least two papers for a comparison."
      : "Select at least one paper to ask a question.";
  }
  const maximum = mode === "research" ? 10 : 50;
  if (count > maximum) {
    const extra = count - maximum;
    return `${mode === "research" ? "Deep research" : "Quick answer"} supports up to ${maximum} papers. Deselect ${extra} ${extra === 1 ? "paper" : "papers"} to continue.`;
  }
  return null;
}
