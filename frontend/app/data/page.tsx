import type { Metadata } from "next";
import { Suspense } from "react";

import { DataView } from "@/features/data/data-view";

export const metadata: Metadata = { title: "Data Preparation & Exploration" };

export default function Page() {
  return (
    <Suspense>
      <DataView />
    </Suspense>
  );
}
