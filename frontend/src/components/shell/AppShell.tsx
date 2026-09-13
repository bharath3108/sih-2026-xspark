"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { IconButton } from "@/components/ui/Button";
import { IconMenu } from "@/components/ui/Icons";
import { API_BASE } from "@/lib/api";
import { SidebarContent, SidebarDrawer } from "./Sidebar";
import { NAV_GROUPS, findLink, isActive } from "./nav-config";

function Breadcrumb() {
  const pathname = usePathname();
  const link = findLink(pathname);
  const group = NAV_GROUPS.find((g) => g.links.some((l) => isActive(pathname, l.href)));
  if (!link) return null;

  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px]">
      {group && (
        <>
          <span className="hidden text-ink-4 sm:inline">{group.label}</span>
          <span aria-hidden="true" className="hidden text-ink-4 sm:inline">
            /
          </span>
        </>
      )}
      <span className="truncate font-medium text-ink-2">{link.label}</span>
    </nav>
  );
}

function SourceIndicator() {
  // Which backend this build talks to — worth surfacing in an investigation
  // tool where the same UI can point at dev fixtures or the live stack.
  let host = API_BASE;
  try {
    host = new URL(API_BASE).host;
  } catch {
    /* keep the raw value if it isn't a parseable URL */
  }

  return (
    <span className="hidden items-center gap-2 rounded-lg border border-line bg-surface-2/60 py-1.5 pr-3 pl-2.5 md:inline-flex">
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ok" />
      </span>
      <span className="text-[11px] text-ink-3">
        API <span className="font-medium text-ink-2">{host}</span>
      </span>
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Navigating closes the drawer via each link's onNavigate; Escape closes it too.
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  return (
    <div className="app-ambient relative min-h-dvh">
      {/* Static sidebar, lg and up */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] border-r border-line bg-base/80 backdrop-blur-xl lg:flex lg:flex-col">
        <SidebarContent />
      </aside>

      <SidebarDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />

      <div className="relative z-10 flex min-h-dvh flex-col lg:pl-[248px]">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b border-line bg-canvas/80 px-4 backdrop-blur-xl sm:px-6">
          <div className="lg:hidden">
            <IconButton
              label="Open navigation"
              onClick={() => setDrawerOpen(true)}
              aria-expanded={drawerOpen}
              variant="secondary"
            >
              <IconMenu className="h-[18px] w-[18px]" />
            </IconButton>
          </div>
          <Breadcrumb />
          <div className="ml-auto flex items-center gap-2">
            <SourceIndicator />
          </div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:py-8">
          <div className="mx-auto w-full max-w-[1400px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
