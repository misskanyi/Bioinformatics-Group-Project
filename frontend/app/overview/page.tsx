import type { Metadata } from "next";

import { OverviewView } from "@/features/research/overview-view";

export const metadata: Metadata = { title: "Research Overview" };

export default function Page() {
  return <OverviewView />;
}
