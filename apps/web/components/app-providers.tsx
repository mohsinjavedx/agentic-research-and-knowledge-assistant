"use client";

import { usePathname } from "next/navigation";
import { BackendReadinessProvider } from "@/components/backend-readiness";
import { SourceLibraryProvider } from "@/components/source-library";
import { PreferencesProvider } from "@/components/preferences";
import { WorkspaceMemoryProvider } from "@/components/workspace-memory";
import { AppShell } from "@/components/app-shell";

export function AppProviders({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const workspace = pathname !== "/" && pathname !== "/about";
  return (
    <PreferencesProvider>
      <WorkspaceMemoryProvider>
        <BackendReadinessProvider enabled={workspace}>
          <SourceLibraryProvider enabled={workspace}>
            <AppShell>{children}</AppShell>
          </SourceLibraryProvider>
        </BackendReadinessProvider>
      </WorkspaceMemoryProvider>
    </PreferencesProvider>
  );
}
