import { LogoMark } from "./logo";

const BASE_PAIRS = 12;

// Fallback when JavaScript is disabled: never show the overlay or hold content back.
const NO_SCRIPT_CSS = ".boot-screen{display:none}.page-stage>*>*,.stagger>*{animation:none!important}";

/**
 * Server-rendered loading overlay. Visible only while the client bundle is
 * still loading (it fades in after 200 ms and lifts when AppShell hydrates
 * and sets html[data-ready]); styles live in globals.css.
 */
export function BootScreen() {
  return (
    <>
      <div className="boot-screen" role="status" aria-live="polite">
        <div className="flex flex-col items-center gap-6 text-center">
          <div className="boot-helix" aria-hidden>
            {Array.from({ length: BASE_PAIRS }, (_, i) => (
              <span key={i} className="boot-bp" style={{ "--i": i } as React.CSSProperties}>
                <span className="boot-r" />
                <span className="boot-a" />
                <span className="boot-b" />
              </span>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <LogoMark className="size-9" />
            <div className="text-left leading-tight">
              <div className="text-[15px] font-semibold tracking-tight text-ink">PET Enzyme Explorer</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-teal/80">Decode · Rethink</div>
            </div>
          </div>
          <div className="flex flex-col items-center gap-2.5">
            <div className="boot-progress" />
            <p className="eyebrow text-[10px]">Loading research workspace</p>
          </div>
        </div>
      </div>
      <noscript>
        <style>{NO_SCRIPT_CSS}</style>
      </noscript>
    </>
  );
}
