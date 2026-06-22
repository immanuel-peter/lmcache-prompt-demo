import type { Metadata } from "next";
import { IBM_Plex_Mono, Syne } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "LMCache Prompt Registry",
  description:
    "Visual demo for decoded KV chunks across GPU, CPU, and external storage tiers.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${syne.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full mesh-bg">
        <div className="pointer-events-none fixed inset-0 grid-overlay" />
        {children}
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "rgba(15, 23, 42, 0.95)",
              border: "1px solid rgba(59, 130, 246, 0.25)",
              color: "#e2e8f0",
              fontFamily: "var(--font-plex-mono)",
            },
          }}
        />
      </body>
    </html>
  );
}
