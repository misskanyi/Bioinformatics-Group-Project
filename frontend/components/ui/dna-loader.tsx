import { cn } from "@/lib/utils";

/** Animated base-pair helix used for genuine loading states (styles: .boot-helix in globals.css). */
export function DnaLoader({ pairs = 12, small, className }: { pairs?: number; small?: boolean; className?: string }) {
  return (
    <div className={cn("boot-helix", small && "is-sm", className)} aria-hidden>
      {Array.from({ length: pairs }, (_, i) => (
        <span key={i} className="boot-bp" style={{ "--i": i } as React.CSSProperties}>
          <span className="boot-r" />
          <span className="boot-a" />
          <span className="boot-b" />
        </span>
      ))}
    </div>
  );
}
