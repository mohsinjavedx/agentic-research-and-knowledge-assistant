"use client";

import { useEffect, useState } from "react";
import { getResearchJob, userFacingApiError, type ResearchJob } from "@/lib/api";

type JobState =
  { kind: "loading" } | { kind: "error"; message: string } | { kind: "loaded"; job: ResearchJob };

export function useResearchJob(id: string, enabled: boolean) {
  const [state, setState] = useState<JobState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let requestTimer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | null = null;
    const started = Date.now();
    async function poll() {
      controller = new AbortController();
      let timedOut = false;
      requestTimer = setTimeout(() => {
        timedOut = true;
        controller?.abort();
      }, 15_000);
      try {
        const job = await getResearchJob(id, controller.signal);
        if (!active) return;
        if (
          (job.status === "running" || job.status === "queued") &&
          Date.now() - started >= 600_000
        ) {
          setState({
            kind: "error",
            message:
              "This run is taking longer than expected. Check its status again, or start a more focused comparison.",
          });
          return;
        }
        setState({ kind: "loaded", job });
        if (job.status === "running" || job.status === "queued")
          pollTimer = setTimeout(() => void poll(), 2000);
      } catch (reason) {
        if (active)
          setState({
            kind: "error",
            message: timedOut
              ? "The status check took too long. Retry to check the run again."
              : userFacingApiError(reason),
          });
      } finally {
        clearTimeout(requestTimer);
      }
    }
    void poll();
    return () => {
      active = false;
      controller?.abort();
      clearTimeout(pollTimer);
      clearTimeout(requestTimer);
    };
  }, [id, enabled, attempt]);
  const current: JobState =
    state.kind === "loaded" && state.job.job_id !== id ? { kind: "loading" } : state;
  function retry() {
    setState({ kind: "loading" });
    setAttempt((value) => value + 1);
  }
  return { state: current, retry };
}
