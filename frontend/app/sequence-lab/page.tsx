import type { Metadata } from "next";
import { Suspense } from "react";

import { SequenceLabView } from "@/features/sequence-lab/sequence-lab-view";

export const metadata: Metadata = { title: "Sequence Laboratory" };

export default function Page() {
  return (
    <Suspense>
      <SequenceLabView />
    </Suspense>
  );
}
