import { redirect } from "next/navigation";

export default async function Page({ searchParams }: { searchParams: Promise<{ protein?: string }> }) {
  const { protein } = await searchParams;
  redirect(`/discovery${protein ? `?protein=${protein}` : ""}`);
}
