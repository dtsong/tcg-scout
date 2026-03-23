import type { Metadata } from "next";
import localFont from "next/font/local";
import { Audiowide, IBM_Plex_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const audiowide = Audiowide({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-display",
  display: "swap",
});

const ibmPlexSans = IBM_Plex_Sans({
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
  title: "Scout | JP Meta Explorer",
  description:
    "Competitive intelligence for the JP Pokemon TCG rotation format. Meta tier list, buy lists, trends, and Champions League results.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${audiowide.variable} ${ibmPlexSans.variable} ${jetbrainsMono.variable} ${pokemonClassic.variable}`}
    >
      <body className="min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
