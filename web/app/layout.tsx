import type { Metadata } from "next";
import localFont from "next/font/local";
import { Roboto, Source_Code_Pro } from "next/font/google";
import "./globals.css";

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

const robotoBody = Roboto({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-body",
  display: "swap",
});

const sourceCodePro = Source_Code_Pro({
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
      className={`${roboto.variable} ${robotoBody.variable} ${sourceCodePro.variable} ${pokemonClassic.variable}`}
    >
      <body className="min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
