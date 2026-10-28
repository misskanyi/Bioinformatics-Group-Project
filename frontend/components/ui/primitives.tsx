"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { AlertTriangle, Info, RotateCw, SearchX } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

import { Button } from "./button";

/* ---------------------------------------------------------------- Panel */
export function Panel({
  className,
  children,
  glow,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { glow?: boolean }) {
  return (
    <div className={cn("panel relative", glow && "glow-ring", className)} {...props}>
      {children}
    </div>
  );
}

export function PanelHeader({
  title,
  eyebrow,
  description,
  action,
  className,
}: {
  title: React.ReactNode;
  eyebrow?: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3 px-5 pt-5", className)}>
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h3 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h3>
        {description && <p className="mt-1 max-w-prose text-[13px] leading-relaxed text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

/* ---------------------------------------------------------------- Badge */
export function Badge({
  color = "#9BB3C6",
  children,
  className,
  dot = true,
}: {
  color?: string;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-5",
        className,
      )}
      style={{ color, borderColor: `${color}55`, background: `${color}14` }}
    >
      {dot && <span className="size-1.5 rounded-full" style={{ background: color }} />}
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------- Skeleton */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("relative overflow-hidden rounded-md bg-elevated/70", className)}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.6s_infinite] bg-gradient-to-r from-transparent via-white/[0.04] to-transparent" />
    </div>
  );
}

/* ---------------------------------------------------------------- Tooltip */
export const TooltipProvider = TooltipPrimitive.Provider;

export function Tip({ content, children, side = "top" }: { content: React.ReactNode; children: React.ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <TooltipPrimitive.Root delayDuration={150}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className="z-50 max-w-xs rounded-lg border border-line bg-[#0d1a2a]/95 px-3 py-2 text-xs leading-relaxed text-ink shadow-xl backdrop-blur"
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

export function InfoTip({ content }: { content: React.ReactNode }) {
  return (
    <Tip content={content}>
      <button type="button" aria-label="More information" className="text-muted/70 transition hover:text-teal">
        <Info className="size-3.5" />
      </button>
    </Tip>
  );
}

/* ---------------------------------------------------------------- Slider */
export function Slider({ className, ...props }: React.ComponentProps<typeof SliderPrimitive.Root>) {
  return (
    <SliderPrimitive.Root className={cn("relative flex h-5 w-full touch-none select-none items-center", className)} {...props}>
      <SliderPrimitive.Track className="relative h-1 grow overflow-hidden rounded-full bg-line">
        <SliderPrimitive.Range className="absolute h-full bg-gradient-to-r from-cyan to-teal" />
      </SliderPrimitive.Track>
      {(props.value ?? props.defaultValue ?? [0]).map((_, i) => (
        <SliderPrimitive.Thumb
          key={i}
          className="block size-4 rounded-full border-2 border-teal bg-void shadow-[0_0_12px_rgb(72_225_205/0.6)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/60"
        />
      ))}
    </SliderPrimitive.Root>
  );
}

/* ---------------------------------------------------------------- Tabs */
export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("inline-flex flex-wrap gap-1 rounded-lg border border-line bg-surface/80 p-1", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "rounded-md px-3 py-1.5 text-xs font-medium text-muted transition hover:text-ink",
        "data-[state=active]:bg-elevated data-[state=active]:text-teal data-[state=active]:shadow-[inset_0_0_0_1px_rgb(72_225_205/0.35)]",
        className,
      )}
      {...props}
    />
  );
}

export const TabsContent = TabsPrimitive.Content;

/* ---------------------------------------------------------------- Inputs */
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-lg border border-line bg-void/70 px-3 text-sm text-ink placeholder:text-muted/60",
        "transition focus:border-teal/60 focus:outline-none focus:ring-2 focus:ring-teal/20",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export function Select({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  label: string;
  className?: string;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "h-9 rounded-lg border border-line bg-void/70 px-2.5 text-sm text-ink focus:border-teal/60 focus:outline-none focus:ring-2 focus:ring-teal/20",
        className,
      )}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value} className="bg-surface">
          {o.label}
        </option>
      ))}
    </select>
  );
}

/* ---------------------------------------------------------------- States */
export function ErrorState({ message, onRetry, className }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn("flex flex-col items-center gap-3 px-6 py-10 text-center", className)}>
      <div className="grid size-11 place-items-center rounded-full border border-amber/40 bg-amber/10 text-amber">
        <AlertTriangle className="size-5" />
      </div>
      <div>
        <p className="font-medium text-ink">Data could not be loaded</p>
        <p className="mt-1 max-w-md text-sm text-muted">{message}</p>
      </div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          <RotateCw /> Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  icon,
  className,
}: {
  title: string;
  children?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-6 py-10 text-center", className)}>
      <div className="grid size-11 place-items-center rounded-full border border-line bg-elevated text-muted">
        {icon ?? <SearchX className="size-5" />}
      </div>
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="max-w-md text-sm leading-relaxed text-muted">{children}</div>}
    </div>
  );
}

export function Notice({ children, tone = "info", className }: { children: React.ReactNode; tone?: "info" | "warn"; className?: string }) {
  const c = tone === "warn" ? "border-amber/30 bg-amber/[0.06] text-amber" : "border-cyan/25 bg-cyan/[0.06] text-cyan";
  return (
    <div className={cn("flex gap-2.5 rounded-lg border px-3.5 py-2.5 text-[13px] leading-relaxed", c, className)}>
      {tone === "warn" ? <AlertTriangle className="mt-0.5 size-4 shrink-0" /> : <Info className="mt-0.5 size-4 shrink-0" />}
      <div className="text-ink/85">{children}</div>
    </div>
  );
}

/* ---------------------------------------------------------------- Metric */
export function Metric({
  label,
  value,
  hint,
  accent = "#48E1CD",
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  accent?: string;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="eyebrow">{label}</div>
      <div className="tabular mt-1 text-2xl font-semibold tracking-tight" style={{ color: accent }}>
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  );
}
