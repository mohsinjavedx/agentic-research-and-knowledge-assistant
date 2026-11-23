"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowUpRight,
  Books,
  ChatCircleText,
  Compass,
  IconContext,
  ShieldCheck,
  StackSimple,
} from "@phosphor-icons/react";
import { useBackendReadiness, WakeUpBanner } from "@/components/backend-readiness";

const links = [
  { href: "/workspace", label: "Workspace", icon: ChatCircleText },
  { href: "/documents", label: "Paper library", icon: Books },
  { href: "/research", label: "Deep research", icon: Compass },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { readiness, retry } = useBackendReadiness();
  const current = links.find((link) => pathname.startsWith(link.href)) ?? links[0];
  const ready = readiness.kind === "ready";
  return (
    <IconContext.Provider value={{ size: 20, weight: "regular" }}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="app-shell">
        <aside className="navigation-rail">
          <Link href="/" className="wordmark" aria-label="Research desk home">
            <span className="brand-symbol">
              <StackSimple weight="duotone" size={25} />
            </span>
            Research desk<span className="brand-period">.</span>
          </Link>
          <div className="rail-content">
            <span className="rail-caption">Your research space</span>
            <nav aria-label="Main navigation">
              {links.map(({ href, label, icon: Icon }) => {
                const active =
                  pathname.startsWith(href) || (pathname === "/" && href === "/workspace");
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`nav-link${active ? " active" : ""}`}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon />
                    {label}
                  </Link>
                );
              })}
            </nav>
            <div className="rail-note">
              <span className="rail-note-icon">
                <Books weight="duotone" size={26} />
              </span>
              <strong>A little more perspective.</strong>
              <p>Three papers. Different fields. One place to connect the dots.</p>
              <Link href="/documents">
                Explore the library <ArrowUpRight size={15} />
              </Link>
            </div>
          </div>
          <div className="rail-footer">
            <span className="avatar">Y</span>
            <div>
              <strong>Your workspace</strong>
              <span>
                <ShieldCheck size={13} /> Private browser session
              </span>
            </div>
          </div>
        </aside>
        <div className="app-content">
          <header className="topbar">
            <div className="breadcrumb">
              <span>Research desk</span>
              <span className="breadcrumb-slash">/</span>
              <strong>{pathname.startsWith("/research/") ? "Research run" : current.label}</strong>
            </div>
            <button
              className={`connection-pill ${ready ? "connected" : ""}`}
              onClick={retry}
              disabled={readiness.kind === "checking"}
              title="Check service connection"
            >
              <span className="status-dot" />
              {ready ? "Connected" : readiness.kind === "checking" ? "Connecting" : "Offline"}
            </button>
          </header>
          <WakeUpBanner />
          <main id="main">{children}</main>
          <footer className="app-footer">
            <span>Made for curious minds.</span>
            <span>Answers with sources you can inspect.</span>
          </footer>
        </div>
      </div>
    </IconContext.Provider>
  );
}
