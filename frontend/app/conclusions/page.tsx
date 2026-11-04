import type { Metadata } from "next";

import { ConclusionsView } from "@/features/conclusions/conclusions-view";

export const metadata: Metadata = { title: "Conclusions & Recommendations" };

export default function Page() {
  return <ConclusionsView />;
}
