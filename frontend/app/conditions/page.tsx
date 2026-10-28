import type { Metadata } from "next";

import { ConditionsView } from "@/features/conditions/conditions-view";

export const metadata: Metadata = { title: "Activity Conditions" };

export default function Page() {
  return <ConditionsView />;
}
