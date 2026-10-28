"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { ChevronRight, CircleHelp, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Tip } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { navFor } from "@/lib/nav";
import { EVIDENCE } from "@/lib/palette";
import { cn } from "@/lib/utils";
import type { Health } from "@/types/api";

type Status = { state: "checking" } | { state: "ready"; health: Health } | { state: "offline"; message: string };

function DatasetStatus() {
  const [status, setStatus] = useState<Status>({ state: "checking" });

  useEffect(() => {
    let live = true;
    const check = () =>
      api
        .get<Health>("/health")
        .then((health) => live && setStatus({ state: "ready", health }))
        .catch((e: Error) => live && setStatus({ state: "offline", message: e.message }));
    check();
    const id = setInterval(check, 30000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, []);

  const color = status.state === "ready" ? "#69E8C3" : status.state === "offline" ? "#E8B56B" : "#9BB3C6";
  const label =
    status.state === "ready" ? `Dataset ready · ${status.health.proteins} proteins` : status.state === "offline" ? "Backend offline" : "Checking backend…";
  const tip =
    status.state === "ready"
      ? "Live health check of the FastAPI backend succeeded: reference proteins and the sequence matcher are loaded."
      : status.state === "offline"
        ? status.message
        : "Contacting /api/health";

  return (
    <Tip content={tip} side="bottom">
      <div
        role="status"
        className="flex h-8 items-center gap-2 rounded-full border px-3 font-mono text-[11px]"
        style={{ borderColor: `${color}40`, color, background: `${color}0f` }}
      >
        <span className="relative flex size-2">
          {status.state === "ready" && <span className="absolute inset-0 animate-ping rounded-full opacity-60" style={{ background: color }} />}
          <span className="relative size-2 rounded-full" style={{ background: color }} />
        </span>
        <span className="hidden sm:inline">{label}</span>
      </div>
    </Tip>
  );
}

function HelpDialog() {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label="Help">
          <CircleHelp />
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-void/70 backdrop-blur-sm" />
        <Dialog.Content className="panel fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[min(560px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto p-6">
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="text-lg font-semibold">How to read this explorer</Dialog.Title>
            <Dialog.Close className="text-muted hover:text-ink" aria-label="Close">
              <X className="size-5" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-2 text-sm leading-relaxed text-muted">
            PET Enzyme Explorer is an evidence browser, not a prediction model. It compares a sequence with 298 experimentally
            characterised PET-active proteins and shows what has been reported about them.
          </Dialog.Description>
          <div className="mt-5 space-y-3">
            {Object.values(EVIDENCE).map((e) => (
              <div key={e.label} className="flex items-start gap-3 text-sm">
                <span className="mt-1.5 size-2.5 shrink-0 rounded-full" style={{ background: e.color }} />
                <div>
                  <div className="font-medium" style={{ color: e.color }}>
                    {e.label}
                  </div>
                  <div className="text-muted">
                    {e.label === EVIDENCE.experimental.label && "Reported PET breakdown in a published assay (PAZy)."}
                    {e.label === EVIDENCE.computational.label && "Alignment identity and coverage. Not evidence of activity."}
                    {e.label === EVIDENCE.organism.label && "Organism from a database record with the same sequence."}
                    {e.label === EVIDENCE.uncertain.label && "No record, or records that disagree. Shown as unknown."}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-5 text-xs text-muted">
            See <Link href="/about#documentation" className="text-teal hover:underline">research documentation</Link> for methods.
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Topbar({ onOpenMobile, className }: { onOpenMobile: () => void; className?: string }) {
  const pathname = usePathname();
  const item = navFor(pathname);
  return (
    <header className={cn("sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line/60 bg-void/75 px-4 backdrop-blur-xl sm:px-6", className)}>
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onOpenMobile} aria-label="Open navigation">
        <Menu />
      </Button>
      <div className="min-w-0">
        <nav aria-label="Breadcrumb" className="flex items-center gap-1 font-mono text-[11px] text-muted">
          <Link href="/dashboard" className="shrink-0 whitespace-nowrap hover:text-teal">
            PET Explorer
          </Link>
          {item && (
            <>
              <ChevronRight className="size-3" />
              <span className="truncate">{item.description}</span>
            </>
          )}
        </nav>
        <h1 className="truncate text-[17px] font-semibold tracking-tight">{item?.label ?? "PET Enzyme Explorer"}</h1>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <DatasetStatus />
        <HelpDialog />
      </div>
    </header>
  );
}
