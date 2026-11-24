"use client";

import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

export type Theme = "dark" | "light" | "system";
const values = new Map<string, string>();
function read(name: string, fallback: string): string {
  try {
    return localStorage.getItem(`research-assistant:${name}`) ?? values.get(name) ?? fallback;
  } catch {
    return values.get(name) ?? fallback;
  }
}
function write(name: string, value: string) {
  values.set(name, value);
  try {
    localStorage.setItem(`research-assistant:${name}`, value);
  } catch {
    /* Preferences still work in memory. */
  }
  window.dispatchEvent(new Event("research-preferences"));
}
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("research-preferences", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("research-preferences", callback);
  };
}
const getTheme = (): Theme => {
  const value = read("theme", "dark");
  return value === "light" || value === "system" ? value : "dark";
};
const getCollapsed = () => read("sidebar", "expanded") === "collapsed";
const subscribeScheme = (callback: () => void) => {
  const query = matchMedia("(prefers-color-scheme: dark)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
};
const getSystemDark = () => matchMedia("(prefers-color-scheme: dark)").matches;
type Preferences = {
  theme: Theme;
  resolvedTheme: "dark" | "light";
  setTheme: (theme: Theme) => void;
  collapsed: boolean;
  toggleSidebar: () => void;
};
const Context = createContext<Preferences | null>(null);

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const theme = useSyncExternalStore(subscribe, getTheme, () => "dark" as const);
  const collapsed = useSyncExternalStore(subscribe, getCollapsed, () => false);
  const systemDark = useSyncExternalStore(subscribeScheme, getSystemDark, () => true);
  const resolvedTheme = theme === "system" ? (systemDark ? "dark" : "light") : theme;
  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.colorScheme = resolvedTheme;
  }, [resolvedTheme]);
  const value = useMemo(
    () => ({
      theme,
      resolvedTheme,
      collapsed,
      setTheme: (value: Theme) => write("theme", value),
      toggleSidebar: () => write("sidebar", collapsed ? "expanded" : "collapsed"),
    }),
    [theme, resolvedTheme, collapsed],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function usePreferences() {
  const value = useContext(Context);
  if (!value) throw new Error("Preferences provider is missing.");
  return value;
}
