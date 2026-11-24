"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { AnswerResponse } from "@/lib/api";

export type Conversation = {
  id: string;
  kind: "answer" | "research";
  query: string;
  documentIds: string[];
  createdAt: string;
  saved: boolean;
  answer?: AnswerResponse;
  jobId?: string;
};
type Memory = {
  conversations: Conversation[];
  activeId: string | null;
  draftVersion: number;
  rememberAnswer: (query: string, ids: string[], answer: AnswerResponse) => string;
  rememberResearch: (query: string, ids: string[], jobId: string) => void;
  activate: (id: string) => void;
  newResearch: () => void;
  toggleSaved: (id: string) => void;
  remove: (id: string) => void;
  forgetDocument: (id: string) => void;
  clear: () => void;
};
const Context = createContext<Memory | null>(null);

export function WorkspaceMemoryProvider({ children }: { children: React.ReactNode }) {
  // Private response text deliberately lives only in React memory, never web storage.
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draftVersion, setDraftVersion] = useState(0);
  const newResearch = useCallback(() => {
    setActiveId(null);
    setDraftVersion((n) => n + 1);
  }, []);
  const rememberAnswer = useCallback((query: string, ids: string[], answer: AnswerResponse) => {
    const id = crypto.randomUUID();
    const entry: Conversation = {
      id,
      kind: "answer",
      query,
      documentIds: [...ids],
      answer,
      saved: false,
      createdAt: new Date().toISOString(),
    };
    setConversations((items) => [entry, ...items].slice(0, 32));
    setActiveId(id);
    return id;
  }, []);
  const rememberResearch = useCallback((query: string, ids: string[], jobId: string) => {
    setConversations((items) =>
      items.some((item) => item.jobId === jobId)
        ? items
        : [
            {
              id: jobId,
              kind: "research" as const,
              query,
              documentIds: [...ids],
              jobId,
              saved: false,
              createdAt: new Date().toISOString(),
            },
            ...items,
          ].slice(0, 32),
    );
  }, []);
  const toggleSaved = useCallback(
    (id: string) =>
      setConversations((items) =>
        items.map((item) => (item.id === id ? { ...item, saved: !item.saved } : item)),
      ),
    [],
  );
  const remove = useCallback((id: string) => {
    setConversations((items) => items.filter((item) => item.id !== id));
    setActiveId((current) => (current === id ? null : current));
  }, []);
  const forgetDocument = useCallback(
    (id: string) => {
      setConversations((items) => items.filter((item) => !item.documentIds.includes(id)));
      setActiveId((current) =>
        conversations.some((item) => item.id === current && item.documentIds.includes(id))
          ? null
          : current,
      );
    },
    [conversations],
  );
  const clear = useCallback(() => {
    setConversations([]);
    newResearch();
  }, [newResearch]);
  const value = useMemo(
    () => ({
      conversations,
      activeId,
      draftVersion,
      rememberAnswer,
      rememberResearch,
      activate: setActiveId,
      newResearch,
      toggleSaved,
      remove,
      forgetDocument,
      clear,
    }),
    [
      conversations,
      activeId,
      draftVersion,
      rememberAnswer,
      rememberResearch,
      newResearch,
      toggleSaved,
      remove,
      forgetDocument,
      clear,
    ],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useWorkspaceMemory() {
  const value = useContext(Context);
  if (!value) throw new Error("Workspace memory provider is missing.");
  return value;
}
