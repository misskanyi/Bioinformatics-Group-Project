"use client";

import { useEffect, useRef } from "react";

// Residue classes used for colouring (standard physicochemical grouping).
const AA_CLASS: Record<string, string> = {
  A: "#69E8C3", V: "#69E8C3", L: "#69E8C3", I: "#69E8C3", M: "#69E8C3", F: "#69E8C3", W: "#69E8C3", P: "#69E8C3", // hydrophobic
  S: "#4CA8D8", T: "#4CA8D8", N: "#4CA8D8", Q: "#4CA8D8", Y: "#4CA8D8", C: "#4CA8D8", G: "#9BB3C6", // polar / glycine
  D: "#EF8A9A", E: "#EF8A9A", // acidic
  K: "#B49CF5", R: "#B49CF5", H: "#B49CF5", // basic
};

/**
 * A slowly rotating helical projection of a real reference sequence.
 * Purely illustrative: residues are wound on an ideal 3.6-residue/turn helix,
 * it is NOT a solved 3D structure.
 */
export function HelixCanvas({ sequence, className }: { sequence: string; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

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
        ctx.strokeStyle = `rgba(72,225,205,${0.08 + 0.22 * ((p.z + q.z) / 2 + 1) / 2})`;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
        ctx.stroke();
      }
      // residues, back to front
      [...pts]
        .sort((a, b) => a.z - b.z)
        .forEach((p) => {
          const depth = (p.z + 1) / 2;
          const r = 1.6 + depth * 3.2;
          ctx.globalAlpha = 0.25 + depth * 0.75;
          ctx.fillStyle = AA_CLASS[p.aa] ?? "#9BB3C6";
          ctx.shadowColor = ctx.fillStyle;
          ctx.shadowBlur = depth * 10;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
          ctx.fill();
          if (depth > 0.82 && w > 500) {
            ctx.shadowBlur = 0;
            ctx.globalAlpha = (depth - 0.82) * 4;
            ctx.fillStyle = "#F0F8FF";
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
  }, [sequence]);

  return <canvas ref={ref} className={className} aria-hidden />;
}

export const AA_LEGEND = [
  { label: "Hydrophobic", color: "#69E8C3" },
  { label: "Polar", color: "#4CA8D8" },
  { label: "Acidic", color: "#EF8A9A" },
  { label: "Basic", color: "#B49CF5" },
  { label: "Glycine", color: "#9BB3C6" },
];
