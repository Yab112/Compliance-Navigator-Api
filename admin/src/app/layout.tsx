import type { Metadata } from "next";
import { Geist_Mono, Noto_Sans, Noto_Sans_Ethiopic } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const notoSans = Noto_Sans({ subsets: ["latin"], variable: "--font-latin" });
const notoEthiopic = Noto_Sans_Ethiopic({ subsets: ["ethiopic"], variable: "--font-ethiopic" });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Admin · Compliance Navigator",
  description: "Staff workspace for Compliance Navigator.",
  // Staff tools stay out of search engines
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${notoSans.variable} ${notoEthiopic.variable}`}>
      <body className={`${geistMono.variable} antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
