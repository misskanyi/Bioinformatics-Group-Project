"use client";

import { useMemo, useSyncExternalStore } from "react";

import { THEME_KEY as KEY } from "./theme-script";

/**
 * Light / dark theme.
 *
 * The theme is a `data-theme` attribute on <html>; every colour is a CSS
 * variable that globals.css redefines for `[data-theme="light"]`. So switching
 * needs no React rerender for anything drawn with CSS or SVG. Only canvas and
 * Cytoscape, which need concrete colour strings, subscribe via `useTheme()`.
 *
 * THEME_SCRIPT runs in <head> before first paint: stored choice, else the
 * system preference. That is what prevents a flash of the wrong theme.
 */

export type Theme = "dark" | "light";

const listeners = new Set<() => void>();
let media: MediaQueryList | null = null;

function current(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function stored(): Theme | null {
  try {
    const t = localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : null;
  } catch {
    return null;
  }
}

function apply(t: Theme) {
  const d = document.documentElement;
  d.dataset.theme = t;
  d.style.colorScheme = t;
  listeners.forEach((l) => l());
}

// Follow the system setting until the user picks a theme explicitly.
function onSystemChange(e: MediaQueryListEvent) {
  if (!stored()) apply(e.matches ? "light" : "dark");
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  if (!media && typeof window !== "undefined" && window.matchMedia) {
    media = window.matchMedia("(prefers-color-scheme: light)");
    media.addEventListener("change", onSystemChange);
  }
  return () => {
    listeners.delete(cb);
    if (!listeners.size && media) {
      media.removeEventListener("change", onSystemChange);
      media = null;
    }
  };
}

/** Current theme. Renders as "dark" during SSR/hydration, then updates (no hydration mismatch). */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, current, () => "dark");
}

/** Switch theme and remember the choice. Crossfades via the View Transitions API where supported. */
export function setTheme(t: Theme) {
  try {
    localStorage.setItem(KEY, t);
  } catch {
    /* storage unavailable: still switch for this visit */
  }
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
  if (!reduce && doc.startViewTransition) doc.startViewTransition(() => apply(t));
  else apply(t);
}

/** Resolve `var(--x)` to its current computed value; other strings pass through. */
export function resolveColor(color: string, fallback = "#a8bdd8"): string {
  const m = /^var\((--[\w-]+)\)$/.exec(color.trim());
  if (!m) return color;
  if (typeof document === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(m[1]).trim() || fallback;
}

/**
 * Concrete colours for canvas / Cytoscape, recomputed when the theme changes.
 * Pass an object of `var(--…)` strings; get the same keys back as hex/rgb.
 */
export function useResolvedColors<T extends Record<string, string>>(vars: T): T {
  const theme = useTheme();
  const key = JSON.stringify(vars);
  return useMemo(
    () => Object.fromEntries(Object.entries(vars).map(([k, v]) => [k, resolveColor(v)])) as T,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme, key],
  );
}
