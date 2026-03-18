import { getCLDivision } from "@/app/lib/data";
import { ChampionsClient } from "./champions-client";

export default function ChampionsPage() {
  const juniors = getCLDivision("juniors");
  const seniors = getCLDivision("seniors");
  const masters = getCLDivision("masters");

  return (
    <ChampionsClient
      divisions={{ juniors, seniors, masters }}
    />
  );
}
