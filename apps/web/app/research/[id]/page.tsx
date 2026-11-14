import Link from "next/link";

export default function Research() {
  return <section className="document-page"><p className="section-label">Research notebook</p><h1>Make room for discovery.</h1><div className="empty-state"><h2>Research workflows are on the roadmap</h2><p>Multi-document comparisons arrive in Phase 6, after retrieval and grounded answers have passed their evaluation gates.</p><Link className="button secondary" href="/workspace">Return to workspace</Link></div></section>;
}
