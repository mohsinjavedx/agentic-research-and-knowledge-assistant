"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getHealth, type Health } from "@/lib/api";

export type Readiness =
  | { kind: "checking" }
  | { kind: "ready"; health: Health }
  | { kind: "not_ready"; health: Health }
  | { kind: "unavailable" }
  | { kind: "timed_out" };

type BackendReadinessValue = {
  readiness: Readiness;
  wakeDelayElapsed: boolean;
  isReady: boolean;
  retry: () => void;
};

const BackendReadinessContext = createContext<BackendReadinessValue | null>(null);

export function BackendReadinessProvider({
  children,
  enabled = true,
}: {
  children: ReactNode;
  enabled?: boolean;
}) {
  const [readiness, setReadiness] = useState<Readiness>({ kind: "checking" });
  const [wakeDelayElapsed, setWakeDelayElapsed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setReadiness({ kind: "checking" });
    setWakeDelayElapsed(false);
    setAttempt((current) => current + 1);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let active = true;
    let timedOut = false;
    const wakeTimer = setTimeout(() => {
      if (active) setWakeDelayElapsed(true);
    }, 3000);
    const deadlineTimer = setTimeout(() => {
      timedOut = true;
      controller.abort();
      if (active) setReadiness({ kind: "timed_out" });
    }, 60000);

    getHealth(controller.signal)
      .then(
        (health) => {
          if (active && !timedOut) {
            setReadiness({
              kind: health.status === "ready" ? "ready" : "not_ready",
              health,
            });
          }
        },
        () => {
          if (active && !timedOut) setReadiness({ kind: "unavailable" });
        },
      )
      .finally(() => {
        clearTimeout(wakeTimer);
        clearTimeout(deadlineTimer);
      });

    return () => {
      active = false;
      clearTimeout(wakeTimer);
      clearTimeout(deadlineTimer);
      controller.abort();
    };
  }, [attempt, enabled]);

  const value = useMemo(
    () => ({
      readiness,
      wakeDelayElapsed,
      isReady: readiness.kind === "ready",
      retry,
    }),
    [readiness, wakeDelayElapsed, retry],
  );

  return (
    <BackendReadinessContext.Provider value={value}>{children}</BackendReadinessContext.Provider>
  );
}

export function useBackendReadiness(): BackendReadinessValue {
  const value = useContext(BackendReadinessContext);
  if (!value) {
    throw new Error("useBackendReadiness must be used within BackendReadinessProvider.");
  }
  return value;
}

export function WakeUpBanner() {
  const { readiness, wakeDelayElapsed, retry } = useBackendReadiness();

  if (readiness.kind === "ready") return null;
  if (readiness.kind === "checking" && !wakeDelayElapsed) return null;

  const message =
    readiness.kind === "checking"
      ? "Waking up the demo server. This can take 30-60 seconds. Research actions unlock when it is ready."
      : readiness.kind === "not_ready"
        ? "The API responded, but its database is not ready. Check the service, then retry."
        : readiness.kind === "timed_out"
          ? "The server is taking longer than expected to wake up. Retry the connection."
          : "The server could not be reached. Check the connection, then retry.";

  return (
    <aside className="wake-banner" role="status" aria-live="polite">
      <p>{message}</p>
      {readiness.kind !== "checking" && (
        <button className="text-button" type="button" onClick={retry}>
          Retry
        </button>
      )}
    </aside>
  );
}
