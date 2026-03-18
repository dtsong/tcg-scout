import { Nav } from "@/app/components/nav";
import { getFormats } from "@/app/lib/data";

export function generateStaticParams() {
  return getFormats().map((f) => ({ format: f.slug }));
}

export default async function FormatLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  return (
    <>
      <Nav format={format} />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
      <footer className="border-t border-surface-700 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-surface-400">
            <p>
              Data sourced from{" "}
              <a href="https://limitlesstcg.com" target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent/80">
                LimitlessTCG
              </a>{" "}
              (City League results) and{" "}
              <a href="https://pokemon-card.com" target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent/80">
                pokemon-card.com
              </a>{" "}
              (Champions League decklists)
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
