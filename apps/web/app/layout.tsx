import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research desk | Knowledge Assistant",
  description: "A research workspace for evidence, sources, and cited answers.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">Skip to content</a>
        <header className="site-header">
          <Link className="wordmark" href="/" aria-label="Research desk home">
            <span className="mark" aria-hidden="true">r<span>.</span></span>
            Research desk
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/workspace">Workspace</Link>
            <Link href="/documents">Documents</Link>
          </nav>
          <span className="phase-tag">Foundation preview</span>
        </header>
        <main id="main">{children}</main>
        <footer>Research & Knowledge Assistant <span>Phase 0 / Local development</span></footer>
      </body>
    </html>
  );
}
