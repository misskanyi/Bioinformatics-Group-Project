"use client";

import { useEffect, useRef, useState } from "react";

import { clusterColor } from "@/lib/palette";
import type { Clustering } from "@/types/api";

// Sequential ramp from the panel colour to teal. Identities at or below FLOOR share the darkest
// colour so differences between related proteins stay visible.
const FLOOR = 20;
function ramp(v: number) {
  const t = Math.min(1, Math.max(0, (v - FLOOR) / (100 - FLOOR)));
  const a = [16, 30, 48];
  const b = [72, 225, 205];
  const c = t < 0.85 ? a.map((x, i) => x + (b[i] - x) * (t / 0.85)) : b.map((x) => x + (240 - x) * ((t - 0.85) / 0.15));
  return `rgb(${c.map(Math.round).join(",")})`;
}

export function IdentityHeatmap({ data }: { data: Clustering["heatmap"] }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<{ i: number; j: number } | null>(null);
  const n = data.ids.length;
  const BAND = 6;

  useEffect(() => {
    const c = ref.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    c.width = n + BAND;
    c.height = n + BAND;
    data.matrix.forEach((row, i) =>
      row.forEach((v, j) => {
        ctx.fillStyle = ramp(v);
        ctx.fillRect(j + BAND, i + BAND, 1, 1);
      }),
    );
    data.subclusters.forEach((s, i) => {
      ctx.fillStyle = clusterColor(s);
      ctx.fillRect(i + BAND, 0, 1, BAND - 1);
      ctx.fillRect(0, i + BAND, BAND - 1, 1);
    });
  }, [data, n]);

  const onMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const scale = (n + BAND) / r.width;
    const j = Math.floor((e.clientX - r.left) * scale) - BAND;
    const i = Math.floor((e.clientY - r.top) * scale) - BAND;
    setHover(i >= 0 && j >= 0 && i < n && j < n ? { i, j } : null);
  };

  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,520px)_1fr]">
      <canvas
        ref={ref}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        className="aspect-square w-full cursor-crosshair rounded-md border border-line/70 [image-rendering:pixelated]"
        role="img"
        aria-label="All-against-all sequence identity heatmap, proteins ordered by subgroup"
      />
      <div className="flex flex-col gap-4 text-sm">
        <div className="min-h-20 rounded-lg border border-line/70 bg-void/50 p-3 font-mono text-xs">
          {hover ? (
            <>
              <div>
                <span style={{ color: clusterColor(data.subclusters[hover.i]) }}>{data.names[hover.i]}</span>
                <span className="text-muted"> ({data.subclusters[hover.i]})</span>
              </div>
              <div>
                <span style={{ color: clusterColor(data.subclusters[hover.j]) }}>{data.names[hover.j]}</span>
                <span className="text-muted"> ({data.subclusters[hover.j]})</span>
              </div>
              <div className="mt-1 text-lg text-teal">{data.matrix[hover.i][hover.j]}% identity</div>
            </>
          ) : (
            <span className="text-muted">Hover the matrix to read a protein pair.</span>
          )}
        </div>
        <div>
          <div className="eyebrow mb-2">Identity scale</div>
          <div className="h-3 rounded-full" style={{ background: `linear-gradient(90deg, ${[20, 40, 60, 80, 100].map(ramp).join(",")})` }} />
          <div className="mt-1 flex justify-between font-mono text-[10px] text-muted">
            <span>≤ 20%</span>
            <span>60%</span>
            <span>100%</span>
          </div>
        </div>
        <p className="text-xs leading-relaxed text-muted">
          Pairwise identity from local alignments of all {n} proteins ({((n * (n - 1)) / 2).toLocaleString()} pairs). Rows and columns are ordered by subgroup (coloured
          bands), then by the first alignment-MDS axis. Bright blocks on the diagonal are coherent sequence families.
        </p>
      </div>
    </div>
  );
}
