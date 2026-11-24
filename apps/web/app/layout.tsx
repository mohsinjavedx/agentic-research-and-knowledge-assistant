import type { Metadata } from "next";
import { AppProviders } from "@/components/app-providers";
import "@fontsource-variable/inter";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research Assistant — Grounded answers. Clearer thinking.",
  description: "A research workspace for evidence, sources, and cited answers.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
