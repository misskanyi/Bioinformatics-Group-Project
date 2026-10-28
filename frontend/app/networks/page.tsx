import type { Metadata } from "next";
import { Suspense } from "react";

import { NetworksView } from "@/features/networks/networks-view";

export const metadata: Metadata = { title: "Protein Networks" };

export default function Page() {
  return (
    <Suspense>
      <NetworksView />
    </Suspense>
  );
}
