import { getMeta } from "@/app/lib/data";
import { ArchetypesClient } from "./archetypes-client";

export default function ArchetypesPage() {
  const meta = getMeta();
  return <ArchetypesClient archetypes={meta.archetypes} />;
}
