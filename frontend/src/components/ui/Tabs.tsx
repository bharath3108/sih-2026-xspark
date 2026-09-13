"use client";

import { useId, useState, type ReactNode } from "react";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
  content: ReactNode;
}

/** Roving-tabindex tab list following the WAI-ARIA tabs pattern. */
export function Tabs({ items, ariaLabel }: { items: TabItem[]; ariaLabel: string }) {
  const base = useId();
  const [active, setActive] = useState(items[0]?.id);

  if (items.length === 0) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    const i = items.findIndex((t) => t.id === active);
    let next = i;
    if (e.key === "ArrowRight") next = (i + 1) % items.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + items.length) % items.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = items.length - 1;
    else return;
    e.preventDefault();
    setActive(items[next].id);
    document.getElementById(`${base}-tab-${items[next].id}`)?.focus();
  };

  return (
    <div>
      <div
        role="tablist"
        aria-label={ariaLabel}
        onKeyDown={onKeyDown}
        className="no-scrollbar flex gap-1 overflow-x-auto rounded-lg bg-surface-2/70 p-1"
      >
        {items.map((t) => {
          const selected = t.id === active;
          return (
            <button
              key={t.id}
              id={`${base}-tab-${t.id}`}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls={`${base}-panel-${t.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(t.id)}
              className={`flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors duration-150 ${
                selected ? "bg-surface text-ink shadow-card" : "text-ink-3 hover:text-ink-2"
              }`}
            >
              {t.label}
              {t.count !== undefined && (
                <span className={`tnum text-[11px] ${selected ? "text-ink-3" : "text-ink-4"}`}>{t.count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Only the active panel is mounted — keeps large payloads out of the DOM
          and out of find-in-page / assistive-tech traversal. */}
      {items
        .filter((t) => t.id === active)
        .map((t) => (
          <div
            key={t.id}
            id={`${base}-panel-${t.id}`}
            role="tabpanel"
            aria-labelledby={`${base}-tab-${t.id}`}
            tabIndex={0}
            className="mt-3 animate-pop-in"
          >
            {t.content}
          </div>
        ))}
    </div>
  );
}
