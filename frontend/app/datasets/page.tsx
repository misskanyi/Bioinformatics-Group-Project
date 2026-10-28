import type { Metadata } from "next";

import { DatasetsView } from "@/features/datasets/datasets-view";

export const metadata: Metadata = { title: "Dataset Intelligence" };

export default function Page() {
  return <DatasetsView />;
}
