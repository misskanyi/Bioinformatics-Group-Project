"use client";

import { ChevronDown, ChevronsLeft, ChevronsRight, X } from "lucide-react";
import { LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Tip } from "@/components/ui/primitives";
import { MAIN_NAV, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { LogoMark } from "./logo";

function NavLink({
  item,
  collapsed,
  active,
  onNavigate,
  className,
}: {
  item: NavItem;
  collapsed: boolean;
  active: boolean;
  onNavigate?: () => void;
  className?: string;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50",
        active ? "text-ink" : "text-muted hover:bg-elevated/60 hover:text-ink",
        collapsed && "justify-center px-0",
        className,
      )}
    >
      {active && (
        <motion.span
          layoutId="nav-active"
          className="absolute inset-0 rounded-lg border border-electric/45 bg-gradient-to-r from-electric/[0.28] via-electric/[0.1] to-cyan/[0.03] shadow-[0_0_20px_-8px_var(--glow-strong)]"
          transition={{ type: "spring", stiffness: 420, damping: 36 }}
        >
          <span className="absolute inset-y-2 left-0 w-[3px] rounded-r-full bg-cyan shadow-[0_0_12px_var(--glow-cyan)]" />
        </motion.span>
      )}
      <Icon
        className={cn(
          "relative size-[18px] shrink-0 transition-[color,transform] duration-200",
          active ? "text-cyan" : "group-hover:text-ink motion-safe:group-hover:scale-110",
        )}
      />
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

type Sections = NonNullable<NavItem["sections"]>;

function SubLinks({ item, sections, current, onNavigate }: { item: NavItem; sections: Sections; current: string | null; onNavigate?: () => void }) {
  return (
    <ul className="relative ml-[21px] flex flex-col gap-0.5 border-l border-line/70 py-1 pl-3">
      {sections.map((s) => {
        const active = s.id === current;
        return (
          <li key={s.id} className="relative">
            {active && <span className="absolute -left-[13.5px] top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full bg-cyan shadow-[0_0_8px_var(--glow-cyan)]" />}
            <Link
              href={`${item.href}?section=${s.id}`}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "block truncate rounded-md px-2.5 py-1.5 text-[13px] transition-colors duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50",
                active ? "bg-electric/[0.12] text-cyan" : "text-muted hover:bg-elevated/60 hover:text-ink",
              )}
            >
              {s.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

// useSearchParams needs a Suspense boundary; the fallback renders the same links without a highlight.
function ActiveSubLinks(props: { item: NavItem; sections: Sections; onNavigate?: () => void }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const onPage = pathname.startsWith(props.item.href);
  const raw = params.get("section");
  const current = onPage ? (props.sections.find((s) => s.id === raw)?.id ?? props.sections[0].id) : null;
  return <SubLinks {...props} current={current} />;
}

function NavGroup({
  item,
  sections,
  active,
  open,
  onToggleOpen,
  onNavigate,
}: {
  item: NavItem;
  sections: Sections;
  active: boolean;
  open: boolean;
  onToggleOpen: () => void;
  onNavigate?: () => void;
}) {
  const id = `subnav-${item.href.slice(1)}`;
  return (
    <div>
      <div className="relative">
        <NavLink item={item} collapsed={false} active={active} onNavigate={onNavigate} className="pr-9" />
        <button
          type="button"
          onClick={onToggleOpen}
          aria-expanded={open}
          aria-controls={id}
          aria-label={`${open ? "Collapse" : "Expand"} ${item.label} sections`}
          className="absolute right-1.5 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-muted transition-colors duration-200 hover:bg-elevated/70 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50"
        >
          <ChevronDown className={cn("size-4 transition-transform duration-300", open && "rotate-180")} />
        </button>
      </div>
      {/* grid-rows 0fr → 1fr animates to the submenu's natural height */}
      <div
        id={id}
        inert={!open}
        className={cn("grid transition-[grid-template-rows,opacity] duration-300 ease-out", open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0")}
      >
        <div className="overflow-hidden">
          <Suspense fallback={<SubLinks item={item} sections={sections} current={null} onNavigate={onNavigate} />}>
            <ActiveSubLinks item={item} sections={sections} onNavigate={onNavigate} />
          </Suspense>
        </div>
      </div>
    </div>
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

  // Submenus open when their page is visited and can be folded by hand.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(MAIN_NAV.filter((n) => n.sections).map((n) => [n.href, isActive(n.href)])),
  );
  useEffect(() => {
    const here = MAIN_NAV.find((n) => n.sections && pathname.startsWith(n.href));
    if (here) setOpenGroups((g) => (g[here.href] ? g : { ...g, [here.href]: true }));
  }, [pathname]);

  const body = (mobile: boolean) => {
    const c = collapsed && !mobile;
    return (
      <div className="flex h-full flex-col">
        <div className={cn("flex h-16 items-center gap-3 px-4", c && "justify-center px-0")}>
          <Link href="/overview" className="flex min-w-0 items-center gap-3" onClick={mobile ? onCloseMobile : undefined}>
            <LogoMark className="size-9 shrink-0" />
            {!c && (
              <div className="min-w-0 leading-tight">
                <div className="truncate text-[15px] font-semibold tracking-tight">PET Enzyme Explorer</div>
                <div className="truncate font-mono text-[10px] uppercase tracking-[0.16em] text-cyan/80">Decode · Rethink</div>
              </div>
            )}
          </Link>
          {mobile && (
            <button onClick={onCloseMobile} className="ml-auto text-muted hover:text-ink" aria-label="Close navigation">
              <X className="size-5" />
            </button>
          )}
        </div>

        <LayoutGroup id={mobile ? "mobile" : "desktop"}>
          <nav aria-label="Main" className="mt-2 flex flex-col gap-1 px-3">
            {!c && <div className="eyebrow mb-1 px-3 text-[10px]">Workspace</div>}
            {MAIN_NAV.map((item) =>
              item.sections && !c ? (
                <NavGroup
                  key={item.href}
                  item={item}
                  sections={item.sections}
                  active={isActive(item.href)}
                  open={!!openGroups[item.href]}
                  onToggleOpen={() => setOpenGroups((g) => ({ ...g, [item.href]: !g[item.href] }))}
                  onNavigate={mobile ? onCloseMobile : undefined}
                />
              ) : (
                <NavLink key={item.href} item={item} collapsed={c} active={isActive(item.href)} onNavigate={mobile ? onCloseMobile : undefined} />
              ),
            )}
          </nav>
        </LayoutGroup>

        <div className="mt-auto flex flex-col gap-1 border-t border-line/70 px-3 py-3">
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
          "fixed inset-y-0 left-0 z-30 hidden border-r border-line/70 bg-gradient-to-b from-surface via-surface/95 to-surface-2/95 shadow-[1px_0_0_0_var(--edge-glow)] transition-[width] duration-300 lg:block",
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
            "absolute inset-y-0 left-0 w-72 border-r border-line bg-gradient-to-b from-surface to-surface-2 transition-transform duration-300",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          {body(true)}
        </aside>
      </div>
    </>
  );
}
