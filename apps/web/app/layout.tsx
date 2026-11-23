import type { Metadata } from "next";
import { BackendReadinessProvider } from "@/components/backend-readiness";
import { AppShell } from "@/components/app-shell";
import { SourceLibraryProvider } from "@/components/source-library";
import "@fontsource-variable/manrope";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research desk | Knowledge Assistant",
  description: "A research workspace for evidence, sources, and cited answers.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <BackendReadinessProvider>
          <SourceLibraryProvider>
            <AppShell>{children}</AppShell>
          </SourceLibraryProvider>
        </BackendReadinessProvider>
      </body>
    </html>
  );
}
