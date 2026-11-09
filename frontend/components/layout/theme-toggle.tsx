"use client";

import { Moon, Sun } from "lucide-react";

import { Tip } from "@/components/ui/primitives";
import { setTheme, useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

/**
 * Sun / moon switch in the top bar. Which icon shows is decided by CSS from
 * html[data-theme] (the `light:` variant), not by React state, so the
 * server-rendered button is already correct before hydration.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const theme = useTheme();
  const next = theme === "light" ? "dark" : "light";
  return (
    <Tip content={`Switch to ${next} mode`} side="bottom">
      <button
        type="button"
        role="switch"
        aria-checked={theme === "light"}
        aria-label="Light mode"
        onClick={() => setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light")}
        className={cn(
          "relative grid size-9 place-items-center overflow-hidden rounded-lg text-muted transition-colors duration-200",
          "hover:bg-elevated/70 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/70",
          className,
        )}
      >
        {/* dark mode shows the moon; light mode the sun. Each rotates in as the other leaves. */}
        <Moon className="absolute size-[18px] transition-[rotate,scale,opacity] duration-300 light:rotate-90 light:scale-50 light:opacity-0" aria-hidden />
        <Sun className="absolute size-[18px] -rotate-90 scale-50 opacity-0 transition-[rotate,scale,opacity] duration-300 light:rotate-0 light:scale-100 light:opacity-100 light:text-amber" aria-hidden />
      </button>
    </Tip>
  );
}
