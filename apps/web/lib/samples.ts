export const SAMPLE_DOCUMENTS = [
  {
    id: "35d86749-bf13-55ac-8008-231937b43bab",
    title: "Educational question answering",
    shortTitle: "Educational QA",
    detail: "Lu and Li, 2025",
  },
  {
    id: "a0fba681-ef99-5f3b-aee3-91ea98269e33",
    title: "Personalized nutrition",
    shortTitle: "Nutrition",
    detail: "Gavai and van Hillegersberg, 2025",
  },
  {
    id: "be12ca47-9e95-56c9-abdc-104a9f7680f5",
    title: "Medical question answering",
    shortTitle: "Medical QA",
    detail: "Zhu et al., 2025",
  },
] as const;

export function sampleDocumentLabel(documentId: string): string {
  const index = SAMPLE_DOCUMENTS.findIndex((document) => document.id === documentId);
  return index < 0 ? "Source" : `Doc ${index + 1}`;
}
