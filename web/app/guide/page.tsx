import { redirect } from "next/navigation";
import { getDefaultFormat } from "@/app/lib/data";

export default function GuidePage() {
  redirect(`/${getDefaultFormat()}/guide`);
}
