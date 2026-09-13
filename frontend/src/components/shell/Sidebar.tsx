"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconClose, IconPulse, IconShield } from "@/components/ui/Icons";
import { IconButton } from "@/components/ui/Button";
import { NAV_GROUPS, isActive } from "./nav-config";

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      {/* Brand */}
      <div className="flex h-14 shrink-0 items-center gap-2.5 px-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-accent-soft text-accent">
          <IconPulse className="h-[18px] w-[18px]" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[13px] leading-4 font-semibold text-ink">Social Media Analytics</span>
          <span className="block truncate text-[11px] leading-4 text-ink-4">Investigator Dashboard</span>
        </span>
      </div>

      {/* Groups */}
      <nav aria-label="Primary" className="no-scrollbar flex-1 overflow-y-auto px-3 py-2">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mb-5 last:mb-0">
            <p className="mb-1.5 px-2.5 text-[10px] font-semibold tracking-[0.1em] text-ink-4 uppercase">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.links.map((link) => {
                const active = isActive(pathname, link.href);
                const Icon = link.icon;
                return (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={`group relative flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[13px] font-medium transition-colors duration-150 ${
                        active
                          ? "bg-brand-soft text-ink"
                          : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                      }`}
                    >
                      {/* Active rail */}
                      <span
                        aria-hidden="true"
                        className={`absolute top-1/2 -left-3 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand transition-opacity duration-150 ${
                          active ? "opacity-100" : "opacity-0"
                        }`}
                      />
                      <Icon
                        className={`h-[18px] w-[18px] shrink-0 transition-colors ${
                          active ? "text-brand" : "text-ink-3 group-hover:text-ink-2"
                        }`}
                      />
                      <span className="truncate">{link.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer — provenance, not a fabricated user account. */}
      <div className="shrink-0 border-t border-line p-3">
        <div className="flex items-start gap-2.5 rounded-xl bg-surface-2/60 px-2.5 py-2.5">
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-ok-soft text-ok">
            <IconShield className="h-4 w-4" />
          </span>
          <span className="min-w-0">
            <span className="block text-[12px] leading-4 font-medium text-ink-2">Evidence-linked</span>
            <span className="block text-[11px] leading-4 text-ink-4">
              Every claim carries source events and model versions.
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}

/** Off-canvas drawer for narrow viewports. */
export function SidebarDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <div
      className={`fixed inset-0 z-50 lg:hidden ${open ? "" : "pointer-events-none"}`}
      aria-hidden={!open}
    >
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-200 ${
          open ? "opacity-100" : "opacity-0"
        }`}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className={`absolute inset-y-0 left-0 flex w-[264px] flex-col border-r border-line bg-base shadow-pop transition-transform duration-250 ease-[cubic-bezier(0.22,1,0.36,1)] ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="absolute top-3 right-3 z-10">
          <IconButton label="Close navigation" onClick={onClose} size="sm">
            <IconClose className="h-4 w-4" />
          </IconButton>
        </div>
        <SidebarContent onNavigate={onClose} />
      </div>
    </div>
  );
}
