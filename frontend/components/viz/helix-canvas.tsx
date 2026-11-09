"use client";

import { useEffect, useRef } from "react";

import { C } from "@/lib/palette";
import { useResolvedColors, useTheme } from "@/lib/theme";

// Residue classes used for colouring (standard physicochemical grouping).
type AaClass = "hydrophobic" | "polar" | "glycine" | "acidic" | "basic";
const AA_CLASS: Record<string, AaClass> = {
  A: "hydrophobic", V: "hydrophobic", L: "hydrophobic", I: "hydrophobic", M: "hydrophobic", F: "hydrophobic", W: "hydrophobic", P: "hydrophobic",
  S: "polar", T: "polar", N: "polar", Q: "polar", Y: "polar", C: "polar", G: "glycine",
  D: "acidic", E: "acidic",
  K: "basic", R: "basic", H: "basic",
};
const CLASS_VARS = { hydrophobic: C.mint, polar: C.sky, glycine: C.muted, acidic: C.rose, basic: C.violet, backbone: C.aqua, label: C.ink };

/**
 * A slowly rotating helical projection of a real reference sequence.
 * Purely illustrative: residues are wound on an ideal 3.6-residue/turn helix,
 * it is NOT a solved 3D structure.
 */
export function HelixCanvas({ sequence, className }: { sequence: string; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const colors = useResolvedColors(CLASS_VARS);
  const light = useTheme() === "light";

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !sequence) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const seq = sequence.slice(0, 140);
    let frame = 0;
    let raf = 0;
    let visible = true;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = canvas.clientWidth * dpr;
      canvas.height = canvas.clientHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting));
    io.observe(canvas);

    const draw = (t: number) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const rot = t * 0.00035;
      const radius = Math.min(h * 0.26, 80);
      const step = (w * 1.1) / seq.length;
      const pts = Array.from(seq, (aa, i) => {
        const a = (i * 2 * Math.PI) / 3.6 + rot;
        return {
          aa,
          x: -w * 0.05 + i * step,
          y: h / 2 + Math.sin(a) * radius * (0.85 + 0.15 * Math.sin(i / 9 + rot)),
          z: Math.cos(a),
        };
      });
      // backbone
      ctx.lineWidth = 1.2;
      for (let i = 1; i < pts.length; i++) {
        const p = pts[i - 1];
        const q = pts[i];
        ctx.strokeStyle = colors.backbone;
        ctx.globalAlpha = (light ? 0.18 : 0.08) + 0.22 * ((p.z + q.z) / 2 + 1) / 2;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      // residues, back to front
      [...pts]
        .sort((a, b) => a.z - b.z)
        .forEach((p) => {
          const depth = (p.z + 1) / 2;
          const r = 1.6 + depth * 3.2;
          ctx.globalAlpha = 0.25 + depth * 0.75;
          ctx.fillStyle = colors[AA_CLASS[p.aa] ?? "glycine"];
          ctx.shadowColor = ctx.fillStyle;
          // glow on navy; on white a glow just looks blurry
          ctx.shadowBlur = light ? 0 : depth * 10;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
          ctx.fill();
          if (depth > 0.82 && w > 500) {
            ctx.shadowBlur = 0;
            ctx.globalAlpha = (depth - 0.82) * 4;
            ctx.fillStyle = colors.label;
            ctx.font = "9px var(--font-geist-mono), monospace";
            ctx.fillText(p.aa, p.x - 3, p.y - r - 4);
          }
        });
      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;
    };

    const loop = (t: number) => {
      if (visible) draw(t);
      frame = requestAnimationFrame(loop);
      raf = frame;
    };
    if (reduce) draw(0);
    else raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
    };
  }, [sequence, colors, light]);

  return <canvas ref={ref} className={className} aria-hidden />;
}

export const AA_LEGEND = [
  { label: "Hydrophobic", color: C.mint },
  { label: "Polar", color: C.sky },
  { label: "Acidic", color: C.rose },
  { label: "Basic", color: C.violet },
  { label: "Glycine", color: C.muted },
];
