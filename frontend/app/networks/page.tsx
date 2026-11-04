import { redirect } from "next/navigation";

// Deep links such as /networks?protein=12 keep working.
export default async function Page({ searchParams }: { searchParams: Promise<{ protein?: string }> }) {
  const { protein } = await searchParams;
  redirect(`/data?section=network${protein ? `&protein=${protein}` : ""}`);
}
