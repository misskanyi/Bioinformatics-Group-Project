// Decorative, continuously moving background layers. Pure SVG + CSS (see the
// "ambient" section of globals.css): every animation is a transform/opacity
// change on a composited layer, so nothing is repainted per frame.
// All geometry is deterministic so server and client markup match.

const W = 1440; // width of one seamless tile, in SVG units

/** A sine wave sampled across one tile; whole periods keep both ends level so tiles join without a seam. */
function wavePath(base: number, amp: number, periods: number, phase: number, close?: number) {
  const steps = periods * 24;
  let d = "";
  for (let i = 0; i <= steps; i++) {
    const x = (i / steps) * W;
    const y = base + amp * Math.sin((2 * Math.PI * periods * x) / W + phase) + amp * 0.35 * Math.sin((4 * Math.PI * periods * x) / W + phase * 2);
    d += `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return close == null ? d : `${d}L${W} ${close}L0 ${close}Z`;
}

const WAVES = [
  { base: 300, amp: 70, periods: 1, phase: 0, stroke: "url(#amb-stroke-a)", width: 1.6, band: true },
  { base: 330, amp: 54, periods: 2, phase: 1.2, stroke: "url(#amb-stroke-b)", width: 1.2, band: false },
  { base: 360, amp: 88, periods: 1, phase: 2.4, stroke: "url(#amb-stroke-a)", width: 1, band: true },
  { base: 280, amp: 40, periods: 3, phase: 4.1, stroke: "url(#amb-stroke-c)", width: 0.9, band: false },
  { base: 390, amp: 62, periods: 2, phase: 5.3, stroke: "url(#amb-stroke-b)", width: 0.8, band: false },
];

function WaveTile({ id }: { id: string }) {
  return (
    <svg viewBox={`0 0 ${W} 600`} preserveAspectRatio="none" className="h-full w-1/2 shrink-0" aria-hidden>
      <defs>
        {/* gradients start and end on the same colour, so adjacent tiles meet seamlessly */}
        <linearGradient id={`amb-stroke-a${id}`} x1="0" x2="1">
          <stop offset="0" style={{ stopColor: "var(--wave-1)" }} />
          <stop offset="0.5" style={{ stopColor: "var(--wave-2)" }} />
          <stop offset="1" style={{ stopColor: "var(--wave-1)" }} />
        </linearGradient>
        <linearGradient id={`amb-stroke-b${id}`} x1="0" x2="1">
          <stop offset="0" style={{ stopColor: "var(--wave-2)" }} />
          <stop offset="0.45" style={{ stopColor: "var(--wave-1)" }} />
          <stop offset="0.75" style={{ stopColor: "var(--wave-3)" }} />
          <stop offset="1" style={{ stopColor: "var(--wave-2)" }} />
        </linearGradient>
        <linearGradient id={`amb-stroke-c${id}`} x1="0" x2="1">
          <stop offset="0" style={{ stopColor: "var(--wave-4)", stopOpacity: 0.6 }} />
          <stop offset="0.5" style={{ stopColor: "var(--wave-1)" }} />
          <stop offset="1" style={{ stopColor: "var(--wave-4)", stopOpacity: 0.6 }} />
        </linearGradient>
        <linearGradient id={`amb-band${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style={{ stopColor: "var(--wave-1)", stopOpacity: 0.14 }} />
          <stop offset="1" style={{ stopColor: "var(--wave-1)", stopOpacity: 0 }} />
        </linearGradient>
      </defs>
      {WAVES.map((w, i) => {
        const stroke = w.stroke.replace(")", `${id})`);
        const d = wavePath(w.base, w.amp, w.periods, w.phase);
        return (
          <g key={i}>
            {w.band && <path d={wavePath(w.base, w.amp, w.periods, w.phase, 600)} fill={`url(#amb-band${id})`} />}
            {/* wide faint copy underneath = soft glow, without an SVG filter */}
            <path d={d} fill="none" stroke={stroke} strokeWidth={w.width * 9} strokeOpacity={0.08} strokeLinecap="round" />
            <path d={d} fill="none" stroke={stroke} strokeWidth={w.width} strokeOpacity={0.85} vectorEffect="non-scaling-stroke" />
          </g>
        );
      })}
    </svg>
  );
}

/** Two identical tiles on a 200%-wide track that slides by half its width, looping without a jump. */
export function FlowingWaves({ className, id = "" }: { className?: string; id?: string }) {
  return (
    <div className={`amb-waves ${className ?? ""}`} aria-hidden>
      <div className="amb-waves-track">
        <WaveTile id={`${id}1`} />
        <WaveTile id={`${id}2`} />
      </div>
    </div>
  );
}

// Golden-angle spread: evenly scattered but fixed positions.
const PARTICLES = Array.from({ length: 22 }, (_, i) => {
  const f = (i * 0.618034) % 1;
  const g = (i * 0.754877 + 0.31) % 1;
  return {
    left: `${(f * 100).toFixed(1)}%`,
    top: `${(8 + g * 84).toFixed(1)}%`,
    size: 2 + ((i * 7) % 4),
    dur: 16 + ((i * 5) % 14),
    delay: -((i * 3.7) % 20),
    color: i % 4 === 0 ? "var(--wave-4)" : i % 3 === 0 ? "var(--wave-2)" : "var(--wave-1)",
  };
});

export function Particles({ count = PARTICLES.length, className }: { count?: number; className?: string }) {
  return (
    <div className={`amb-particles ${className ?? ""}`} aria-hidden>
      {PARTICLES.slice(0, count).map((p, i) => (
        <span
          key={i}
          style={
            {
              left: p.left,
              top: p.top,
              width: p.size,
              height: p.size,
              background: p.color,
              boxShadow: `0 0 ${p.size * 3}px ${p.color}`,
              animationDuration: `${p.dur}s`,
              animationDelay: `${p.delay}s`,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}

/**
 * Decorative double helix (not a structure): two phase-shifted sine strands
 * with base-pair rungs, scrolling sideways so it appears to turn.
 */
export function DnaStrip({ className }: { className?: string }) {
  const H = 80;
  const mid = H / 2;
  const amp = 22;
  const period = 120;
  // rounded: unrounded trig output can differ in the last bits between server and browser, breaking hydration
  const r2 = (v: number) => Math.round(v * 100) / 100;
  const y = (x: number, s: number) => r2(mid + s * amp * Math.sin((2 * Math.PI * x) / period));
  const strand = (s: number) => {
    let d = "";
    for (let x = 0; x <= W; x += 6) d += `${x ? "L" : "M"}${x} ${y(x, s)}`;
    return d;
  };
  const rungs = Array.from({ length: W / 20 }, (_, i) => i * 20 + 10);
  const tile = (key: number) => (
    <svg key={key} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className="h-full w-1/2 shrink-0" aria-hidden>
      <path d={strand(1)} fill="none" style={{ stroke: "var(--wave-2)" }} strokeOpacity="0.55" strokeWidth="1.2" />
      <path d={strand(-1)} fill="none" style={{ stroke: "var(--wave-1)" }} strokeOpacity="0.55" strokeWidth="1.2" />
      {rungs.map((x) => {
        const depth = r2((Math.cos((2 * Math.PI * x) / period) + 1) / 2); // 1 = front
        return (
          <g key={x}>
            <line x1={x} x2={x} y1={y(x, 1)} y2={y(x, -1)} style={{ stroke: "var(--wave-4)" }} strokeOpacity={r2(0.12 + depth * 0.2)} strokeWidth="1" />
            <circle cx={x} cy={y(x, 1)} r={r2(1.4 + depth * 1.8)} style={{ fill: "var(--wave-2)" }} fillOpacity={r2(0.35 + depth * 0.6)} />
            <circle cx={x} cy={y(x, -1)} r={r2(1.4 + (1 - depth) * 1.8)} style={{ fill: "var(--wave-1)" }} fillOpacity={r2(0.35 + (1 - depth) * 0.6)} />
          </g>
        );
      })}
    </svg>
  );
  return (
    <div className={`amb-dna ${className ?? ""}`} aria-hidden>
      <div className="amb-dna-track">
        {tile(1)}
        {tile(2)}
      </div>
    </div>
  );
}

/**
 * Fixed full-viewport backdrop behind the whole app: drifting radial glows,
 * flowing light waves and a few floating particles. `calm` dims everything
 * for the data-heavy pages.
 */
export function AmbientBackground({ intensity }: { intensity: "full" | "calm" }) {
  return (
    <div className="ambient" data-intensity={intensity} aria-hidden>
      <div className="amb-glow amb-glow-a" />
      <div className="amb-glow amb-glow-b" />
      <div className="amb-glow amb-glow-c" />
      {/* faint scientific mesh: light theme only (globals.css) */}
      <div className="amb-mesh" />
      <FlowingWaves className="amb-waves-page" id="page" />
      <Particles />
    </div>
  );
}
