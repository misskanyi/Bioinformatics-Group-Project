"use client";

import { ChevronsLeft, ChevronsRight, X } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tip } from "@/components/ui/primitives";
import { FOOTER_NAV, MAIN_NAV, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { LogoMark } from "./logo";

function NavLink({ item, collapsed, active, onNavigate }: { item: NavItem; collapsed: boolean; active: boolean; onNavigate?: () => void }) {
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors",
        active ? "text-ink" : "text-muted hover:bg-elevated/60 hover:text-ink",
        collapsed && "justify-center px-0",
      )}
    >
      {active && (
        <motion.span
          layoutId="nav-active"
          className="absolute inset-0 rounded-lg border border-teal/30 bg-gradient-to-r from-teal/[0.14] to-teal/[0.02]"
          transition={{ type: "spring", stiffness: 420, damping: 36 }}
        >
          <span className="absolute inset-y-2 left-0 w-[3px] rounded-r-full bg-teal shadow-[0_0_12px_#48E1CD]" />
        </motion.span>
      )}
      <Icon className={cn("relative size-[18px] shrink-0", active ? "text-teal" : "group-hover:text-ink")} />
      {!collapsed && <span className="relative truncate">{item.label}</span>}
    </Link>
  );
  return collapsed ? (
    <Tip content={item.label} side="right">
      {link}
    </Tip>
  ) : (
    link
  );
}

export function Sidebar({
  collapsed,
  onToggle,
  mobileOpen,
  onCloseMobile,
}: {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  const pathname = usePathname();
  const isActive = (href: string) => pathname.startsWith(href.split("#")[0]) && !href.includes("#");

  const body = (mobile: boolean) => {
    const c = collapsed && !mobile;
    return (
      <div className="flex h-full flex-col">
        <div className={cn("flex h-16 items-center gap-3 px-4", c && "justify-center px-0")}>
          <Link href="/dashboard" className="flex min-w-0 items-center gap-3" onClick={mobile ? onCloseMobile : undefined}>
            <LogoMark className="size-9 shrink-0" />
            {!c && (
              <div className="min-w-0 leading-tight">
                <div className="truncate text-[15px] font-semibold tracking-tight">PET Enzyme Explorer</div>
                <div className="truncate font-mono text-[10px] uppercase tracking-[0.16em] text-teal/80">Decode · Rethink</div>
              </div>
            )}
          </Link>
          {mobile && (
            <button onClick={onCloseMobile} className="ml-auto text-muted hover:text-ink" aria-label="Close navigation">
              <X className="size-5" />
            </button>
          )}
        </div>

        <nav aria-label="Main" className="mt-2 flex flex-col gap-1 px-3">
          {!c && <div className="eyebrow mb-1 px-3 text-[10px]">Workspace</div>}
          {MAIN_NAV.map((item) => (
            <NavLink key={item.href} item={item} collapsed={c} active={isActive(item.href)} onNavigate={mobile ? onCloseMobile : undefined} />
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-1 border-t border-line/70 px-3 py-3">
          {FOOTER_NAV.map((item) => (
            <NavLink key={item.href} item={item} collapsed={c} active={false} onNavigate={mobile ? onCloseMobile : undefined} />
          ))}
          {!mobile && (
            <button
              onClick={onToggle}
              className={cn(
                "mt-1 flex h-9 items-center gap-3 rounded-lg px-3 text-xs text-muted transition hover:bg-elevated/60 hover:text-ink",
                c && "justify-center px-0",
              )}
              aria-label={c ? "Expand sidebar" : "Collapse sidebar"}
            >
              {c ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
              {!c && "Collapse"}
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden border-r border-line/70 bg-surface/80 backdrop-blur-xl transition-[width] duration-300 lg:block",
          collapsed ? "w-[72px]" : "w-64",
        )}
      >
        {body(false)}
      </aside>

      {/* mobile drawer */}
      <div className={cn("fixed inset-0 z-40 lg:hidden", mobileOpen ? "pointer-events-auto" : "pointer-events-none")}>
        <div
          className={cn("absolute inset-0 bg-void/70 backdrop-blur-sm transition-opacity", mobileOpen ? "opacity-100" : "opacity-0")}
          onClick={onCloseMobile}
        />
        <aside
          className={cn(
            "absolute inset-y-0 left-0 w-72 border-r border-line bg-surface transition-transform duration-300",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          {body(true)}
        </aside>
      </div>
    </>
  );
}
