import type { Metadata } from "next";
import { Suspense } from "react";

import { DiscoveryView } from "@/features/discovery/discovery-view";

export const metadata: Metadata = { title: "Enzyme Prediction & Discovery" };

export default function Page() {
  return (
    <Suspense>
      <DiscoveryView />
    </Suspense>
  );
}
