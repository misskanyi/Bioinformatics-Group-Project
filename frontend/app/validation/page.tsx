import type { Metadata } from "next";

import { ValidationView } from "@/features/validation/validation-view";

export const metadata: Metadata = { title: "Model Validation" };

export default function Page() {
  return <ValidationView />;
}
