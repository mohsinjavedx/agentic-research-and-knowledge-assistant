"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowUpRight,
  Bookmark,
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Database,
  Files,
  History,
  Menu,
  MessageSquare,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sun,
  UserRound,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { ModalDialog } from "@/components/modal-dialog";
import { usePreferences } from "@/components/preferences";
import { useSourceLibrary } from "@/components/source-library";
import { useWorkspaceMemory } from "@/components/workspace-memory";
import { useBackendReadiness, WakeUpBanner } from "@/components/backend-readiness";

const links = [
  { href: "/workspace", label: "Workspace", icon: MessageSquare },
  { href: "/history", label: "Recent conversations", icon: History },
  { href: "/documents", label: "My documents", icon: Files },
  { href: "/knowledge", label: "Knowledge base", icon: Database },
  { href: "/saved", label: "Saved research", icon: Bookmark },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { collapsed, toggleSidebar, resolvedTheme, setTheme } = usePreferences();
  const { readiness, retry } = useBackendReadiness();
  const { documents, loaded } = useSourceLibrary();
  const { newResearch } = useWorkspaceMemory();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collectionOpen, setCollectionOpen] = useState(true);
  const publicPage = pathname === "/" || pathname === "/about";
  const searchDocuments = useCallback(() => {
    const field = document.querySelector<HTMLInputElement>('input[aria-label="Search documents"]');
    if (field) field.focus();
    else router.push("/knowledge");
  }, [router]);
  useEffect(() => {
    if (publicPage) return;
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchDocuments();
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [searchDocuments, publicPage]);
  if (publicPage) return <>{children}</>;
  const current = pathname.startsWith("/research/")
    ? "Research run"
    : pathname === "/research"
      ? "Agentic research"
      : pathname === "/settings"
        ? "Settings"
        : (links.find((item) => item.href === pathname)?.label ?? "Workspace");
  const ready = readiness.kind === "ready";

  function navigation(mobile: boolean) {
    const compact = collapsed && !mobile;
    const close = () => setMobileOpen(false);
    return (
      <>
        <Link
          href="/"
          className="sidebar-brand"
          aria-label="Research Assistant home"
          onClick={close}
        >
          <Brand compact={compact} />
        </Link>
        <Link
          className="new-research-button"
          href="/workspace"
          title="New research"
          onClick={() => {
            newResearch();
            close();
          }}
        >
          <Plus size={18} />
          <span className="nav-label">New research</span>
        </Link>
        <span className="sidebar-section-label nav-label">Research</span>
        <nav aria-label={mobile ? "Mobile workspace" : "Main navigation"}>
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={close}
              title={compact ? label : undefined}
              aria-label={label}
              className={`nav-link${pathname === href ? " active" : ""}`}
              aria-current={pathname === href ? "page" : undefined}
            >
              <Icon size={18} />
              <span className="nav-label">{label}</span>
              {href === "/documents" && loaded && !compact && (
                <span className="nav-count">{documents.length}</span>
              )}
            </Link>
          ))}
          <Link
            href="/research"
            aria-label="Agentic research"
            title={compact ? "Agentic research" : undefined}
            className={`nav-link${pathname.startsWith("/research") ? " active" : ""}`}
            onClick={() => {
              newResearch();
              close();
            }}
          >
            <BrainCircuit size={18} />
            <span className="nav-label">Agentic research</span>
          </Link>
        </nav>
        {!compact && (
          <div className="sidebar-collection">
            <button
              className="sidebar-section-toggle"
              onClick={() => setCollectionOpen((value) => !value)}
              aria-expanded={collectionOpen}
            >
              Current collection{" "}
              <ChevronDown size={14} className={collectionOpen ? "" : "is-closed"} />
            </button>
            {collectionOpen && (
              <div className="sidebar-papers">
                {loaded ? (
                  documents.slice(0, 3).map((paper) => (
                    <Link href="/knowledge" key={paper.id} onClick={close}>
                      <span className="status-dot ready" />
                      <span>{paper.shortTitle}</span>
                    </Link>
                  ))
                ) : (
                  <span className="muted">Connecting your library…</span>
                )}
                {loaded && !documents.length && <span className="muted">Add your first PDF</span>}
              </div>
            )}
          </div>
        )}
        <div className="sidebar-bottom">
          <Link
            href="/settings"
            className={`nav-link${pathname === "/settings" ? " active" : ""}`}
            title="Settings"
            onClick={close}
          >
            <Settings2 size={18} />
            <span className="nav-label">Settings</span>
          </Link>
          <Link href="/about" className="nav-link" title="Help & documentation" onClick={close}>
            <CircleHelp size={18} />
            <span className="nav-label">Help & documentation</span>
            <ArrowUpRight size={13} className="nav-label" />
          </Link>
          <Link
            href="/settings"
            className="session-profile"
            aria-label="Session settings"
            title="Private browser session"
            onClick={close}
          >
            <span className="avatar">
              <UserRound size={18} />
            </span>
            <span className="nav-label">
              <strong>Your workspace</strong>
              <small>
                <ShieldCheck size={11} /> Private browser session
              </small>
            </span>
          </Link>
        </div>
      </>
    );
  }
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className={`app-shell${collapsed ? " is-collapsed" : ""}`}>
        <aside className="navigation-rail">{navigation(false)}</aside>
        <div className="app-content">
          <header className="topbar">
            <div className="header-leading">
              <button
                className="icon-button desktop-nav-toggle"
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                onClick={toggleSidebar}
              >
                {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
              </button>
              <button
                className="icon-button mobile-nav-toggle"
                aria-label="Open navigation"
                onClick={() => setMobileOpen(true)}
              >
                <Menu size={20} />
              </button>
              <div className="breadcrumb">
                <span>Research</span>
                <ChevronRight size={12} />
                <strong>{current}</strong>
              </div>
            </div>
            <div className="header-actions">
              <button
                className="header-search"
                aria-label="Search documents"
                onClick={searchDocuments}
              >
                <Search size={15} />
                <span>Search your knowledge</span>
                <kbd>Ctrl K</kbd>
              </button>
              <button
                className={`connection-pill ${ready ? "connected" : ""}`}
                onClick={retry}
                disabled={readiness.kind === "checking"}
                title="Check service connection"
              >
                <span className="status-dot" />
                <span>
                  {ready ? "Connected" : readiness.kind === "checking" ? "Connecting" : "Offline"}
                </span>
              </button>
              <span className="header-divider" />
              <button
                className="icon-button"
                aria-label={
                  resolvedTheme === "light" ? "Switch to dark theme" : "Switch to light theme"
                }
                title="Toggle appearance"
                onClick={() => setTheme(resolvedTheme === "light" ? "dark" : "light")}
              >
                {resolvedTheme === "light" ? <Moon size={17} /> : <Sun size={17} />}
              </button>
            </div>
          </header>
          <WakeUpBanner />
          <main id="main">{children}</main>
        </div>
      </div>
      <ModalDialog
        open={mobileOpen}
        title="Workspace navigation"
        className="mobile-navigation"
        onClose={() => setMobileOpen(false)}
      >
        {navigation(true)}
      </ModalDialog>
    </>
  );
}
