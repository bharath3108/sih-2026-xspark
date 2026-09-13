import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  children,
}: {
  title: string;
  description?: string;
  eyebrow?: ReactNode;
  /** Primary page actions, right-aligned on wide viewports. */
  actions?: ReactNode;
  /** Filter bar or tabs, rendered under the title block. */
  children?: ReactNode;
}) {
  return (
    <header className="mb-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {eyebrow}
          <h1 className="text-[22px] leading-8 font-semibold tracking-[-0.01em] text-ink">{title}</h1>
          {description && <p className="mt-1 max-w-2xl text-[13px] leading-5 text-ink-3">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </header>
  );
}

/** Horizontal control strip: selects, toggles and the like. */
export function FilterBar({ children, note }: { children: ReactNode; note?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface/60 px-3 py-2.5">
      {children}
      {note && <span className="ml-auto text-[12px] text-ink-4">{note}</span>}
    </div>
  );
}
