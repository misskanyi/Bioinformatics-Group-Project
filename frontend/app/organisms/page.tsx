import type { Metadata } from "next";

import { OrganismsView } from "@/features/organisms/organisms-view";

export const metadata: Metadata = { title: "Organism Explorer" };

export default function Page() {
  return <OrganismsView />;
}
