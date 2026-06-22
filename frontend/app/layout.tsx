import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const geist = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
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
      className={`${geist.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="app-bg min-h-full">
        {children}
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0c0e12",
              border: "1px solid rgba(255,255,255,0.1)",
              color: "#e7eaee",
              fontFamily: "var(--font-geist)",
              fontSize: "13px",
              borderRadius: "10px",
            },
          }}
        />
      </body>
    </html>
  );
}
