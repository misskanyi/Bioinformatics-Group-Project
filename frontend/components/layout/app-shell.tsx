"use client";

import { MotionConfig } from "motion/react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { TooltipProvider } from "@/components/ui/primitives";
import { AmbientBackground } from "@/components/viz/ambient";
import { cn } from "@/lib/utils";

import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

const KEY = "pet-explorer:sidebar-collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    // hydrated: lift the boot screen and release the page entrance animations
    document.documentElement.dataset.ready = "";
    try {
      setCollapsed(localStorage.getItem(KEY) === "1");
    } catch {
      /* storage unavailable */
    }
  }, []);

  const toggle = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem(KEY, c ? "0" : "1");
      } catch {
        /* storage unavailable */
      }
      return !c;
    });

  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider>
        {/* stays mounted across navigation; only its intensity changes */}
        <AmbientBackground intensity={pathname.startsWith("/overview") ? "full" : "calm"} />
        <Sidebar collapsed={collapsed} onToggle={toggle} mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
        <div className={cn("min-h-screen transition-[padding] duration-300", collapsed ? "lg:pl-[72px]" : "lg:pl-64")}>
          <Topbar onOpenMobile={() => setMobileOpen(true)} />
          {/* keyed per route: only the page content remounts, so its staggered entrance (globals.css) plays once per visit */}
          <main key={pathname} className="page-stage mx-auto w-full max-w-[1600px] px-4 pb-16 pt-6 sm:px-6 lg:px-8">
            {children}
          </main>
        </div>
      </TooltipProvider>
    </MotionConfig>
  );
}
