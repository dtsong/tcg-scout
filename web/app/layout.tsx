import type { Metadata } from "next";
import localFont from "next/font/local";
import { Outfit, JetBrains_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

const outfitBody = Outfit({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-body",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-mono",
  display: "swap",
});

const pokemonClassic = localFont({
  src: "../public/fonts/pokemon-classic.ttf",
  variable: "--font-pokemon",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://scout.trainerlab.io"),
  title: "Scout | JP Meta Explorer",
  description:
    "Competitive intelligence for the JP Pokemon TCG rotation format. Meta tier list, buy lists, trends, and Champions League results.",
  openGraph: {
    siteName: "Scout",
    type: "website",
    images: [
      {
        url: "/og-default.png",
        width: 1200,
        height: 630,
        alt: "Scout - JP Meta Explorer for Pokemon TCG",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${outfit.variable} ${outfitBody.variable} ${jetbrainsMono.variable} ${pokemonClassic.variable}`}
    >
      <body className="min-h-screen antialiased">
        {children}
        <Analytics />
      </body>
    </html>
  );
}
