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
import { useWorkspaceMemory } from "@/components/workspace-memory";
import {
  ensureResearchSession,
  listDocuments,
  uploadDocument,
  deleteDocument,
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
  filename?: string;
};
type LibraryValue = {
  documents: LibraryDocument[];
  selectedIds: string[];
  setSelectedIds: React.Dispatch<React.SetStateAction<string[]>>;
  addDocument: (document: DocumentSummary) => void;
  error: string;
  refresh: () => void;
  loaded: boolean;
  removeDocument: (id: string) => void;
  uploadFile: (file: File) => Promise<DocumentSummary>;
  deletePrivateDocument: (id: string) => Promise<void>;
  uploading: boolean;
  deletingIds: string[];
  mutationError: string;
};
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
    filename: document.filename,
  };
}

export function SourceLibraryProvider({
  children,
  enabled = true,
}: {
  children: React.ReactNode;
  enabled?: boolean;
}) {
  const { isReady } = useBackendReadiness();
  const { forgetDocument } = useWorkspaceMemory();
  const forget = useRef(forgetDocument);
  useEffect(() => {
    forget.current = forgetDocument;
  }, [forgetDocument]);
  const [documents, setDocuments] = useState<LibraryDocument[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingIds, setDeletingIds] = useState<string[]>([]);
  const [mutationError, setMutationError] = useState("");
  const uploadInFlight = useRef(false);
  const deletionsInFlight = useRef(new Set<string>());
  const knownDocuments = useRef<LibraryDocument[]>([]);
  const removed = useRef(new Map<string, number>());
  const revision = useRef(0);
  const hasLoaded = useRef(false);
  const hasInteracted = useRef(false);
  const recentUploads = useRef(new Map<string, { revision: number; paper: LibraryDocument }>());
  const refresh = useCallback(() => setAttempt((value) => value + 1), []);
  const addDocument = useCallback((document: DocumentSummary) => {
    hasInteracted.current = true;
    const paper = toLibraryDocument(document);
    removed.current.delete(paper.id);
    revision.current += 1;
    recentUploads.current.set(paper.id, { revision: revision.current, paper });
    knownDocuments.current = [
      ...knownDocuments.current.filter((item) => item.id !== paper.id),
      paper,
    ];
    setDocuments(knownDocuments.current);
    setSelectedIds((current) => (current.includes(paper.id) ? current : [...current, paper.id]));
  }, []);
  const removeDocument = useCallback((id: string) => {
    hasInteracted.current = true;
    revision.current += 1;
    removed.current.set(id, revision.current);
    recentUploads.current.delete(id);
    knownDocuments.current = knownDocuments.current.filter((item) => item.id !== id);
    setDocuments(knownDocuments.current);
    setSelectedIds((items) => items.filter((item) => item !== id));
  }, []);
  // Confirmed mutations belong to the persistent provider, not a route's lifetime.
  const uploadFile = useCallback(
    async (file: File) => {
      if (uploadInFlight.current)
        throw new Error("A PDF is already being indexed. Wait for it to finish.");
      uploadInFlight.current = true;
      setUploading(true);
      setMutationError("");
      try {
        await ensureResearchSession();
        const result = await uploadDocument(file, new AbortController().signal);
        addDocument(result);
        return result;
      } catch (reason) {
        setMutationError(userFacingApiError(reason));
        refresh(); // A timeout/network failure does not prove that the server rolled back.
        throw reason;
      } finally {
        uploadInFlight.current = false;
        setUploading(false);
      }
    },
    [addDocument, refresh],
  );
  const deletePrivateDocument = useCallback(
    async (id: string) => {
      const paper = knownDocuments.current.find((item) => item.id === id);
      if (!paper || paper.isSample) throw new Error("Choose a private upload to delete.");
      if (deletionsInFlight.current.has(id))
        throw new Error("This document is already being deleted.");
      deletionsInFlight.current.add(id);
      setDeletingIds([...deletionsInFlight.current]);
      setMutationError("");
      try {
        await deleteDocument(id, new AbortController().signal);
        removeDocument(id);
        forget.current(id);
      } catch (reason) {
        setMutationError(userFacingApiError(reason));
        refresh();
        throw reason;
      } finally {
        deletionsInFlight.current.delete(id);
        setDeletingIds([...deletionsInFlight.current]);
      }
    },
    [removeDocument, refresh],
  );
  useEffect(() => {
    if (!isReady || !enabled) return;
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
            [...result.map(toLibraryDocument), ...addedWhileReading]
              .filter((paper) => (removed.current.get(paper.id) ?? -1) <= readRevision)
              .map((paper) => [paper.id, paper]),
          ).values(),
        ];
        const available = new Set(merged.map((paper) => paper.id));
        for (const paper of knownDocuments.current) {
          if (!paper.isSample && !available.has(paper.id)) forget.current(paper.id);
        }
        knownDocuments.current = merged;
        setDocuments(merged);
        const chooseDefaults = !hasLoaded.current && !hasInteracted.current;
        hasLoaded.current = true;
        setLoaded(true);
        recentUploads.current.clear();
        setSelectedIds((current) =>
          chooseDefaults && current.length === 0
            ? SAMPLE_DOCUMENTS.map((paper) => paper.id).filter((id) => available.has(id))
            : current.filter((id) => available.has(id)),
        );
      })
      .catch((reason) => {
        if (active) setError(userFacingApiError(reason));
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [isReady, attempt, enabled]);
  const value = useMemo(
    () => ({
      documents,
      selectedIds,
      setSelectedIds,
      addDocument,
      removeDocument,
      loaded,
      error,
      refresh,
      uploadFile,
      deletePrivateDocument,
      uploading,
      deletingIds,
      mutationError,
    }),
    [
      documents,
      selectedIds,
      addDocument,
      removeDocument,
      loaded,
      error,
      refresh,
      uploadFile,
      deletePrivateDocument,
      uploading,
      deletingIds,
      mutationError,
    ],
  );
  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>;
}

export function useSourceLibrary() {
  const library = useContext(LibraryContext);
  if (!library) throw new Error("Source library provider is missing.");
  return library;
}
