import type { Metadata } from "next";
import { Geist_Mono, Noto_Sans, Noto_Sans_Ethiopic } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/layout/app-shell";

const notoSans = Noto_Sans({ subsets: ["latin"], variable: "--font-latin" });
// Amharic (Ge'ez script), falls through from Noto Sans per glyph
const notoEthiopic = Noto_Sans_Ethiopic({ subsets: ["ethiopic"], variable: "--font-ethiopic" });

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Compliance Navigator · የአገልግሎት መመሪያ",
  description:
    "Structured guidance through Ethiopian business registration and regulatory requirements.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${notoSans.variable} ${notoEthiopic.variable}`}>
      <body className={`${geistMono.variable} antialiased`}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
