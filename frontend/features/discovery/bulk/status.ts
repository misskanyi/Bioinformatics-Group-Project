import { C } from "@/lib/palette";
import type { BatchRecord, BatchResult } from "@/types/api";

export const RECORD_STATUS: Record<BatchRecord["status"], { label: string; color: string }> = {
  valid: { label: "Valid", color: C.mint },
  invalid: { label: "Invalid", color: C.rose },
  duplicate: { label: "Duplicate", color: C.amber },
};

export const RESULT_STATUS: Record<BatchResult["status"], { label: string; color: string }> = {
  analysed: { label: "Analysed", color: C.mint },
  duplicate: { label: "Duplicate", color: C.amber },
  invalid: { label: "Invalid", color: C.rose },
  error: { label: "Analysis error", color: C.violet },
};
