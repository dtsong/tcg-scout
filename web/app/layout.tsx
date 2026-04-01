import type { Metadata } from "next";
import localFont from "next/font/local";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

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
  const shouldEnableAnalytics = process.env.NODE_ENV === "production" && Boolean(process.env.VERCEL);

  return (
    <html lang="en" className={pokemonClassic.variable}>
      <body className="min-h-screen antialiased">
        {children}
        {shouldEnableAnalytics ? <Analytics /> : null}
      </body>
    </html>
  );
}
