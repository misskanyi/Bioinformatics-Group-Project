"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export interface ScatterPoint {
  id: number;
  x: number;
  y: number;
  color: string;
  group: string;
  label: string;
}

/** ~`count` round tick values covering [lo, hi]. */
function niceTicks(lo: number, hi: number, count = 5) {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return { ticks: out, step };
}

const fmtTick = (v: number, step: number) => (step >= 1 ? v.toFixed(0) : v.toFixed(Math.min(3, Math.ceil(-Math.log10(step)))));

const M = { l: 52, r: 14, t: 12, b: 44 };

/**
 * Responsive SVG scatter plot built for exploration rather than decoration.
 *
 * - Points are keyed by id, so a new projection, colouring or filter moves /
 *   recolours / fades the same SVG nodes with CSS transitions (globals.css,
 *   `.sp-point`) instead of remounting them: the eye can follow each protein.
 * - Entrance: points pop in once, sweeping left to right.
 * - Hover uses nearest-point search (no pixel hunting on 4 px dots), click
 *   selects; the keyboard can step through points with the arrow keys.
 * - Hidden points stay in place at very low opacity, so filtering never
 *   rescales the axes under the reader.
 */
export function ScatterPlot({
  points,
  xLabel,
  yLabel,
  hidden,
  emphasis,
  selectedId,
  onSelect,
  renderTooltip,
  ariaLabel,
  className,
  radius = 4,
}: {
  points: ScatterPoint[];
  xLabel: string;
  yLabel: string;
  /** groups filtered out */
  hidden?: Set<string>;
  /** group to emphasise (others dim) */
  emphasis?: string | null;
  selectedId?: number | null;
  onSelect?: (id: number | null) => void;
  renderTooltip: (p: ScatterPoint) => React.ReactNode;
  ariaLabel: string;
  className?: string;
  radius?: number;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [hoverId, setHoverId] = useState<number | null>(null);
  const [keyboard, setKeyboard] = useState(false);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Axes fit the data with a 6% margin and round ticks.
  const scale = useMemo(() => {
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const pad = (lo: number, hi: number) => {
      const d = (hi - lo || 1) * 0.06;
      return [lo - d, hi + d] as const;
    };
    const [x0, x1] = pad(Math.min(...xs), Math.max(...xs));
    const [y0, y1] = pad(Math.min(...ys), Math.max(...ys));
    const iw = Math.max(1, size.w - M.l - M.r);
    const ih = Math.max(1, size.h - M.t - M.b);
    return {
      x: (v: number) => M.l + ((v - x0) / (x1 - x0)) * iw,
      y: (v: number) => M.t + (1 - (v - y0) / (y1 - y0)) * ih,
      xt: niceTicks(x0, x1, Math.max(3, Math.round(iw / 90))),
      yt: niceTicks(y0, y1, Math.max(3, Math.round(ih / 60))),
      x0,
      x1,
      iw,
      ih,
    };
  }, [points, size]);

  const visible = useMemo(() => points.filter((p) => !hidden?.has(p.group)).sort((a, b) => a.x - b.x || a.y - b.y), [points, hidden]);
  const byId = useMemo(() => new Map(points.map((p) => [p.id, p])), [points]);

  // Clear a hover that points at a filtered-out protein.
  useEffect(() => {
    if (hoverId != null && hidden?.has(byId.get(hoverId)?.group ?? "")) setHoverId(null);
  }, [hidden, hoverId, byId]);

  const nearest = (mx: number, my: number) => {
    let best: ScatterPoint | null = null;
    let bd = 22 * 22;
    for (const p of visible) {
      const dx = scale.x(p.x) - mx;
      const dy = scale.y(p.y) - my;
      const d = dx * dx + dy * dy;
      if (d < bd) {
        bd = d;
        best = p;
      }
    }
    return best;
  };

  const local = (e: React.MouseEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top] as const;
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (!visible.length) return;
    const i = visible.findIndex((p) => p.id === hoverId);
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      setKeyboard(true);
      setHoverId(visible[(i + 1) % visible.length].id);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      setKeyboard(true);
      setHoverId(visible[(i - 1 + visible.length) % visible.length].id);
    } else if ((e.key === "Enter" || e.key === " ") && hoverId != null) {
      e.preventDefault();
      onSelect?.(hoverId === selectedId ? null : hoverId);
    } else if (e.key === "Escape") {
      setHoverId(null);
      onSelect?.(null);
    }
  };

  const hover = hoverId != null ? byId.get(hoverId) : undefined;
  const sel = selectedId != null ? byId.get(selectedId) : undefined;
  const ready = size.w > 0 && size.h > 0;
  const span = scale.x1 - scale.x0 || 1;

  // tooltip placement: right of the point, flipped near the right edge
  const tip = hover && ready ? { x: scale.x(hover.x), y: scale.y(hover.y), flip: scale.x(hover.x) > size.w - 220 } : null;

  return (
    <div ref={wrap} className={cn("relative h-full w-full", className)}>
      {ready && (
        <svg
          width={size.w}
          height={size.h}
          role="img"
          aria-label={ariaLabel}
          tabIndex={0}
          onKeyDown={onKey}
          onBlur={() => keyboard && setHoverId(null)}
          onMouseMove={(e) => {
            setKeyboard(false);
            setHoverId(nearest(...local(e))?.id ?? null);
          }}
          onMouseLeave={() => setHoverId(null)}
          onClick={(e) => {
            const p = nearest(...local(e));
            onSelect?.(p ? (p.id === selectedId ? null : p.id) : null);
          }}
          // mouse clicks don't take focus, so the focus ring appears only for keyboard users
          onMouseDown={(e) => e.preventDefault()}
          className={cn("block rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50", hover && "cursor-pointer")}
        >
          {/* grid + ticks */}
          <g className="font-mono" fontSize={10}>
            {scale.xt.ticks.map((t) => (
              <g key={`x${t}`}>
                <line x1={scale.x(t)} x2={scale.x(t)} y1={M.t} y2={M.t + scale.ih} stroke="var(--chart-grid)" strokeOpacity={0.4} strokeDasharray="2 4" />
                <text x={scale.x(t)} y={M.t + scale.ih + 16} textAnchor="middle" fill="var(--color-muted)">
                  {fmtTick(t, scale.xt.step)}
                </text>
              </g>
            ))}
            {scale.yt.ticks.map((t) => (
              <g key={`y${t}`}>
                <line x1={M.l} x2={M.l + scale.iw} y1={scale.y(t)} y2={scale.y(t)} stroke="var(--chart-grid)" strokeOpacity={0.4} strokeDasharray="2 4" />
                <text x={M.l - 8} y={scale.y(t) + 3} textAnchor="end" fill="var(--color-muted)">
                  {fmtTick(t, scale.yt.step)}
                </text>
              </g>
            ))}
            <line x1={M.l} x2={M.l + scale.iw} y1={M.t + scale.ih} y2={M.t + scale.ih} stroke="var(--chart-grid)" />
            <line x1={M.l} x2={M.l} y1={M.t} y2={M.t + scale.ih} stroke="var(--chart-grid)" />
          </g>
          <text x={M.l + scale.iw / 2} y={size.h - 6} textAnchor="middle" fontSize={11} fill="var(--color-muted)">
            {xLabel}
          </text>
          <text transform={`translate(13 ${M.t + scale.ih / 2}) rotate(-90)`} textAnchor="middle" fontSize={11} fill="var(--color-muted)">
            {yLabel}
          </text>

          {/* points: stable keys so transforms / fills transition */}
          <g className="sp-enter">
            {points.map((p) => {
              const off = hidden?.has(p.group);
              const dim = !off && emphasis != null && emphasis !== p.group;
              return (
                <g
                  key={p.id}
                  className="sp-point"
                  style={
                    {
                      transform: `translate(${scale.x(p.x)}px, ${scale.y(p.y)}px)`,
                      opacity: off ? 0.05 : dim ? 0.18 : 0.85,
                      "--d": `${Math.round(((p.x - scale.x0) / span) * 450)}ms`,
                    } as React.CSSProperties
                  }
                >
                  <circle r={radius} style={{ fill: p.color }} />
                </g>
              );
            })}
          </g>

          {/* selection and hover rings drawn on top */}
          {sel && !hidden?.has(sel.group) && (
            <g className="sp-point" style={{ transform: `translate(${scale.x(sel.x)}px, ${scale.y(sel.y)}px)` }} pointerEvents="none">
              <circle r={radius + 5} fill="none" stroke="var(--color-ink)" strokeWidth={1.5} />
              <circle r={radius + 1} style={{ fill: sel.color }} stroke="var(--color-void)" strokeWidth={1} />
            </g>
          )}
          {hover && (
            <g style={{ transform: `translate(${scale.x(hover.x)}px, ${scale.y(hover.y)}px)` }} pointerEvents="none">
              <circle r={radius + 2.5} style={{ fill: hover.color }} stroke="var(--color-ink)" strokeWidth={1.5} />
            </g>
          )}
        </svg>
      )}
      {tip && hover && (
        <div
          className="pointer-events-none absolute z-10 transition-[left,top] duration-100"
          style={{ left: tip.flip ? undefined : tip.x + 12, right: tip.flip ? size.w - tip.x + 12 : undefined, top: Math.max(0, tip.y - 20) }}
        >
          {renderTooltip(hover)}
        </div>
      )}
      <p className="sr-only" aria-live="polite">
        {keyboard && hover ? `${hover.label}, ${hover.group}` : ""}
      </p>
    </div>
  );
}
