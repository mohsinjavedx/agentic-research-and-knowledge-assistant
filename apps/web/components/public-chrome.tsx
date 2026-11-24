"use client";

import Link from "next/link";
import { useRef, useState, useSyncExternalStore } from "react";
import { ArrowUpRight, Code2, Menu, X } from "lucide-react";
import { Brand } from "@/components/brand";
import { REPOSITORY_URL } from "@/lib/product";

const publicLinks = [
  ["Product", "/#product"],
  ["Features", "/#features"],
  ["How it works", "/#how-it-works"],
  ["Technology", "/#technology"],
  ["About", "/about"],
];
const subscribe = (callback: () => void) => {
  window.addEventListener("scroll", callback, { passive: true });
  return () => window.removeEventListener("scroll", callback);
};

export function PublicNavbar() {
  const scrolled = useSyncExternalStore(
    subscribe,
    () => window.scrollY > 12,
    () => false,
  );
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  return (
    <header
      className={`public-navbar${scrolled ? " is-scrolled" : ""}`}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          setOpen(false);
          toggle.current?.focus();
        }
      }}
    >
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="public-nav-inner">
        <Link href="/" aria-label="Research Assistant home">
          <Brand />
        </Link>
        <nav className="public-links" aria-label="Public navigation">
          {publicLinks.map(([label, href]) => (
            <Link key={label} href={href}>
              {label}
            </Link>
          ))}
        </nav>
        <div className="public-actions">
          <Link className="text-button public-open" href="/workspace">
            Open workspace
          </Link>
          <Link className="button compact" href="/workspace">
            Get started <ArrowUpRight size={15} />
          </Link>
          <button
            ref={toggle}
            className="icon-button public-menu-toggle"
            aria-label={open ? "Close navigation" : "Open navigation"}
            aria-expanded={open}
            aria-controls="public-mobile-nav"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
      {open && (
        <nav
          id="public-mobile-nav"
          className="public-mobile-nav"
          aria-label="Mobile public navigation"
        >
          {publicLinks.map(([label, href]) => (
            <Link key={label} href={href} onClick={() => setOpen(false)}>
              {label}
              <ArrowUpRight size={15} />
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="public-footer">
      <div className="public-footer-main">
        <div>
          <Link href="/" aria-label="Research Assistant home">
            <Brand />
          </Link>
          <p>
            A clearer path from your documents
            <br />
            to answers you can trace.
          </p>
        </div>
        <div>
          <h3>Explore</h3>
          <Link href="/workspace">Research workspace</Link>
          <Link href="/#features">Features</Link>
          <Link href="/#technology">Technology</Link>
        </div>
        <div>
          <h3>Project</h3>
          <Link href="/about">About & architecture</Link>
          <Link href="/about#documentation">Documentation</Link>
          <a href={REPOSITORY_URL} target="_blank" rel="noopener noreferrer">
            Source code <ArrowUpRight size={12} />
          </a>
        </div>
      </div>
      <div className="public-footer-bottom">
        <span>© {new Date().getFullYear()} Research Assistant</span>
        <a href={REPOSITORY_URL} target="_blank" rel="noopener noreferrer">
          <Code2 size={14} /> Built by mohsinjavedx <ArrowUpRight size={12} />
        </a>
        <span>Grounded answers. Clearer thinking.</span>
      </div>
    </footer>
  );
}
