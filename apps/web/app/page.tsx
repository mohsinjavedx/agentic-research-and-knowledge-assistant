import Link from "next/link";
import { ServiceStatus } from "@/components/service-status";

export default function Home() {
  return (
    <div className="home-grid">
      <section className="introduction">
        <p className="section-label">A place for careful inquiry</p>
        <h1>Keep the evidence<br />in view.</h1>
        <p className="lede">Bring your papers together. Trace ideas back to their sources. Build answers you can inspect.</p>
        <Link className="button" href="/workspace">Open the workspace</Link>
        <p className="preview-note">The foundation is ready to explore. Document upload and research tools are coming in the next phases.</p>
      </section>
      <aside className="desk-sheet" aria-label="Project status">
        <div className="sheet-top"><span>Research notebook</span><span>Phase 0</span></div>
        <h2>A sound foundation.</h2>
        <p>The first step toward research grounded in original sources.</p>
        <ServiceStatus />
        <div className="next-step"><span>Next in the notebook</span><strong>Document ingestion</strong><p>Read text-based PDFs with their layout and page references intact.</p></div>
      </aside>
    </div>
  );
}
