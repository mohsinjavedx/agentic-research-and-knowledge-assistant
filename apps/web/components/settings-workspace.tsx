"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowUpRight,
  Monitor,
  Moon,
  Settings2,
  ShieldCheck,
  Sun,
  Trash2,
  UserRound,
} from "lucide-react";
import { usePreferences, type Theme } from "@/components/preferences";
import { useWorkspaceMemory } from "@/components/workspace-memory";
import { ModalDialog } from "@/components/modal-dialog";
import { ServiceStatus } from "@/components/service-status";
import { REPOSITORY_URL } from "@/lib/product";

export function SettingsWorkspace() {
  const { theme, setTheme, collapsed, toggleSidebar } = usePreferences();
  const { clear, conversations } = useWorkspaceMemory();
  const [confirm, setConfirm] = useState(false);
  const [feedback, setFeedback] = useState("");
  return (
    <section className="settings-page page-enter">
      <header className="page-heading">
        <div>
          <span className="context-label">
            <Settings2 size={15} />
            Make space for your work
          </span>
          <h1>Settings</h1>
          <p>Your workspace preferences, session, and privacy controls.</p>
        </div>
      </header>
      <div className="settings-grid">
        <nav className="settings-nav" aria-label="Settings sections">
          {[
            ["Session", "session"],
            ["Appearance", "appearance"],
            ["Preferences", "preferences"],
            ["Data & privacy", "privacy"],
            ["About", "application"],
          ].map(([title, id]) => (
            <a href={`#${id}`} key={id}>
              {title}
            </a>
          ))}
        </nav>
        <div className="settings-content">
          <section className="settings-section" id="session">
            <h2>Your session</h2>
            <p>
              This workspace uses an anonymous browser session. No account or password is required.
              Private document access follows the session cookie.
            </p>
            <div className="session-card">
              <span className="avatar">
                <UserRound size={20} />
              </span>
              <div>
                <strong>Private browser session</strong>
                <small>Included papers + your session’s own uploads</small>
              </div>
              <ShieldCheck size={18} className="accent-text" />
            </div>
          </section>
          <section className="settings-section" id="appearance">
            <h2>Appearance</h2>
            <p>Choose a comfortable setting for your reading and research.</p>
            <div className="appearance-options">
              {(
                [
                  { value: "dark", label: "Dark", icon: Moon },
                  { value: "light", label: "Light", icon: Sun },
                  { value: "system", label: "System", icon: Monitor },
                ] as const
              ).map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  aria-pressed={theme === value}
                  onClick={() => setTheme(value as Theme)}
                >
                  <Icon size={22} />
                  {label}
                </button>
              ))}
            </div>
          </section>
          <section className="settings-section" id="preferences">
            <h2>Interface preferences</h2>
            <p>Keep the navigation close, or give your research more room.</p>
            <div className="setting-row">
              <div>
                <strong>Compact sidebar</strong>
                <small>This preference is saved in your browser.</small>
              </div>
              <button className="button secondary" aria-pressed={collapsed} onClick={toggleSidebar}>
                {collapsed ? "Expand navigation" : "Use compact navigation"}
              </button>
            </div>
          </section>
          <section className="settings-section" id="privacy">
            <h2>Data & privacy</h2>
            <p>
              Private uploads are available only to the current browser session and expire within 24
              hours. Included papers are shared samples. Delete private documents from My documents
              to remove their indexed passages.
            </p>
            <p>
              Conversation snapshots and bookmarks live only in memory in this tab, with up to 32
              recent items. Refreshing clears them. Only appearance and sidebar preferences are
              saved to browser storage. Questions are sent independently with the selected document
              scope.
            </p>
            <div className="setting-row">
              <div>
                <strong>Clear this tab’s activity</strong>
                <small>
                  {conversations.length} recent {conversations.length === 1 ? "item" : "items"}.
                  Source documents stay in your library.
                </small>
              </div>
              <button
                className="button secondary"
                disabled={!conversations.length}
                onClick={() => setConfirm(true)}
              >
                <Trash2 size={14} />
                Clear activity
              </button>
            </div>
            <div className="setting-row">
              <Link className="text-button accent-text" href="/documents">
                Manage private documents <ArrowUpRight size={14} />
              </Link>
            </div>
            {feedback && (
              <p className="notice success" role="status">
                {feedback}
              </p>
            )}
          </section>
          <section className="settings-section" id="application">
            <h2>About this application</h2>
            <p>
              Research Assistant pairs document retrieval with structured answer generation and
              verifiable source citations.
            </p>
            <div className="tech-badges">
              <span>Next.js</span>
              <span>FastAPI</span>
              <span>pgvector</span>
              <span>BGE</span>
              <span>LangGraph</span>
            </div>
            <div className="setting-row">
              <Link className="text-button accent-text" href="/about">
                Architecture & documentation <ArrowUpRight size={14} />
              </Link>
              <a
                className="text-button"
                href={REPOSITORY_URL}
                target="_blank"
                rel="noopener noreferrer"
              >
                Source code <ArrowUpRight size={14} />
              </a>
            </div>
            <ServiceStatus />
          </section>
        </div>
      </div>
      <ModalDialog
        open={confirm}
        title="Clear this tab’s activity?"
        onClose={() => setConfirm(false)}
      >
        <p>
          This removes all recent questions, answer snapshots, and bookmarks from this tab. Uploaded
          documents and server-side research jobs remain available according to their session access
          and expiry.
        </p>
        <div className="modal-actions">
          <button className="button secondary" onClick={() => setConfirm(false)}>
            Cancel
          </button>
          <button
            className="button danger"
            onClick={() => {
              clear();
              setConfirm(false);
              setFeedback("This tab’s research activity was cleared.");
            }}
          >
            Clear activity
          </button>
        </div>
      </ModalDialog>
    </section>
  );
}
