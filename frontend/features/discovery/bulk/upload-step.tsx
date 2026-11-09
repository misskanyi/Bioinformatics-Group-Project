"use client";

import { ClipboardPaste, FileUp, Loader2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import type { BatchLimits } from "@/types/api";

export interface Upload {
  filename: string;
  content_base64: string;
  size: number;
}

const ACCEPT = ".csv,.tsv,.xlsx,.fasta,.fa,.faa,.fas,.txt,.pdf";

/** Reads a file as base64 for the JSON upload. The browser never interprets the content. */
export function readUpload(file: File): Promise<Upload> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve({ filename: file.name, content_base64: String(r.result).split(",")[1] ?? "", size: file.size });
    r.onerror = () => reject(r.error ?? new Error("The file could not be read."));
    r.readAsDataURL(file);
  });
}

export function UploadStep({
  limits,
  busy,
  error,
  onUpload,
}: {
  limits?: BatchLimits;
  busy: boolean;
  error?: string;
  onUpload: (u: Upload) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [paste, setPaste] = useState("");
  const [localError, setLocalError] = useState<string>();
  const maxBytes = (limits?.max_file_mb ?? 5) * 1024 * 1024;

  const take = async (file?: File | null) => {
    setLocalError(undefined);
    if (!file) return;
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (!ACCEPT.split(",").includes(ext)) return setLocalError("Unsupported file type. Use CSV, TSV, Excel (.xlsx), FASTA, TXT or PDF.");
    if (file.size > maxBytes) return setLocalError(`File is larger than ${limits?.max_file_mb ?? 5} MB.`);
    try {
      onUpload(await readUpload(file));
    } catch (e) {
      setLocalError((e as Error).message);
    }
  };

  const shown = localError ?? error;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Bulk analysis · step 1"
        title="Upload protein sequences"
        description={`Up to ${limits?.max_records ?? 500} sequences of ${limits?.min_length ?? 30}–${limits?.max_length ?? 5000} amino acids. Files are read in memory for this session only and are not stored.`}
      />
      <div className="grid gap-4 p-5 lg:grid-cols-2">
        <button
          type="button"
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            take(e.dataTransfer.files[0]);
          }}
          disabled={busy}
          className={cn(
            "group flex min-h-48 flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-6 text-center transition duration-200",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50 disabled:opacity-60",
            drag ? "border-cyan bg-cyan/[0.08]" : "border-line bg-void/40 hover:border-electric/60 hover:bg-elevated/50",
          )}
        >
          <span className="grid size-12 place-items-center rounded-full border border-electric/40 bg-electric/10 text-cyan transition group-hover:scale-105">
            {busy ? <Loader2 className="size-5 animate-spin" /> : <FileUp className="size-5" />}
          </span>
          <span className="font-medium">{busy ? "Reading file…" : "Drop a file here or choose one"}</span>
          <span className="text-xs text-muted">CSV · TSV · Excel (.xlsx) · FASTA (.fasta, .fa) · TXT · text-based PDF · max {limits?.max_file_mb ?? 5} MB</span>
        </button>
        <input ref={input} type="file" accept={ACCEPT} className="hidden" onChange={(e) => take(e.target.files?.[0])} />

        <div className="flex flex-col gap-2">
          <label htmlFor="bulk-paste" className="eyebrow">
            Or paste FASTA / one sequence per block
          </label>
          <textarea
            id="bulk-paste"
            value={paste}
            onChange={(e) => setPaste(e.target.value)}
            spellCheck={false}
            placeholder={">protein_1 [Organism name]\nMNFPRASRLMQAAVLGGLMAVSAAAT…\n>protein_2\n…"}
            className="min-h-36 flex-1 resize-y rounded-lg border border-line bg-void/70 p-3 font-mono text-xs text-ink placeholder:text-muted/60 focus:border-electric/70 focus:outline-none focus:ring-2 focus:ring-electric/25"
          />
          <Button
            size="sm"
            disabled={!paste.trim() || busy}
            onClick={() => take(new File([paste], paste.trimStart().startsWith(">") ? "pasted.fasta" : "pasted.txt", { type: "text/plain" }))}
            className="self-end"
          >
            <ClipboardPaste /> Read pasted sequences
          </Button>
        </div>
      </div>
      {shown && (
        <p role="alert" className="mx-5 mb-5 rounded-lg border border-amber/40 bg-amber/[0.07] px-3.5 py-2.5 text-[13px] text-ink/90">
          {shown}
        </p>
      )}
    </Panel>
  );
}
