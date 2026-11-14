import Link from "next/link";
import { ServiceStatus } from "@/components/service-status";

export default function Workspace() {
  return <div className="workspace-grid">
    <section><p className="section-label">Your workspace</p><h1>Start with a source.</h1>
      <p className="lede">Your papers, questions, and evidence will come together here.</p>
      <div className="empty-state"><h2>No documents yet</h2><p>PDF ingestion arrives in Phase 1. Once it is connected, you will be able to add papers and follow their processing status.</p><Link className="button secondary" href="/documents">View document library</Link></div>
    </section><aside className="connection-panel"><h2>Connection</h2><ServiceStatus /><p className="preview-note">This checks database readiness and model settings. Model inference is introduced in later phases.</p></aside>
  </div>;
}
