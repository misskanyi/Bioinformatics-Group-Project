import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AppShell } from "@/components/layout/app-shell";
import { BootScreen } from "@/components/layout/boot-screen";
import { THEME_SCRIPT } from "@/lib/theme-script";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#070f1e" },
    { media: "(prefers-color-scheme: light)", color: "#f4f8ff" },
  ],
};

export const metadata: Metadata = {
  title: { default: "PET Enzyme Explorer", template: "%s · PET Enzyme Explorer" },
  description:
    "Explore experimentally characterised PET-degrading enzymes through sequence matching, similarity networks, assay conditions and documented organisms.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // data-theme / color-scheme are set by THEME_SCRIPT before React hydrates, hence suppressHydrationWarning.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <BootScreen />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
