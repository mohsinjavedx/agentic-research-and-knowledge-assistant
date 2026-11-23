"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useBackendReadiness } from "@/components/backend-readiness";
import {
  ensureResearchSession,
  listDocuments,
  type DocumentSummary,
  userFacingApiError,
} from "@/lib/api";
import { SAMPLE_DOCUMENTS } from "@/lib/samples";

export type LibraryDocument = {
  id: string;
  title: string;
  shortTitle: string;
  detail: string;
  isSample: boolean;
  pages?: number;
};
type LibraryValue = {
  documents: LibraryDocument[];
  selectedIds: string[];
  setSelectedIds: React.Dispatch<React.SetStateAction<string[]>>;
  addDocument: (document: DocumentSummary) => void;
  error: string;
  refresh: () => void;
};
const initial: LibraryDocument[] = SAMPLE_DOCUMENTS.map((paper) => ({ ...paper, isSample: true }));
const LibraryContext = createContext<LibraryValue | null>(null);

function toLibraryDocument(document: DocumentSummary): LibraryDocument {
  const sample = SAMPLE_DOCUMENTS.find((paper) => paper.id === document.document_id);
  return {
    id: document.document_id,
    title: sample?.title ?? document.filename,
    shortTitle: sample?.shortTitle ?? document.filename,
    detail: sample?.detail ?? "Your private PDF",
    isSample: document.is_sample,
    pages: document.page_count ?? undefined,
  };
}

export function SourceLibraryProvider({ children }: { children: React.ReactNode }) {
  const { isReady } = useBackendReadiness();
  const [documents, setDocuments] = useState(initial);
  const [selectedIds, setSelectedIds] = useState<string[]>(() => initial.map((paper) => paper.id));
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const revision = useRef(0);
  const recentUploads = useRef(new Map<string, { revision: number; paper: LibraryDocument }>());
  const refresh = useCallback(() => setAttempt((value) => value + 1), []);
  const addDocument = useCallback((document: DocumentSummary) => {
    const paper = toLibraryDocument(document);
    revision.current += 1;
    recentUploads.current.set(paper.id, { revision: revision.current, paper });
    setDocuments((current) => [...current.filter((item) => item.id !== paper.id), paper]);
    setSelectedIds((current) => (current.includes(paper.id) ? current : [...current, paper.id]));
  }, []);
  useEffect(() => {
    if (!isReady) return;
    const controller = new AbortController();
    const readRevision = revision.current;
    let active = true;
    void ensureResearchSession()
      .then(() => listDocuments(controller.signal))
      .then((result) => {
        if (!active) return;
        setError("");
        const addedWhileReading = [...recentUploads.current.values()]
          .filter((entry) => entry.revision > readRevision)
          .map((entry) => entry.paper);
        const merged = [
          ...new Map(
            [...result.map(toLibraryDocument), ...addedWhileReading].map((paper) => [
              paper.id,
              paper,
            ]),
          ).values(),
        ];
        setDocuments(merged);
        recentUploads.current.clear();
        const available = new Set(merged.map((paper) => paper.id));
        setSelectedIds((current) => current.filter((id) => available.has(id)));
      })
      .catch((reason) => {
        if (active) setError(userFacingApiError(reason));
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [isReady, attempt]);
  const value = useMemo(
    () => ({ documents, selectedIds, setSelectedIds, addDocument, error, refresh }),
    [documents, selectedIds, addDocument, error, refresh],
  );
  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>;
}

export function useSourceLibrary() {
  const library = useContext(LibraryContext);
  if (!library) throw new Error("Source library provider is missing.");
  return library;
}
