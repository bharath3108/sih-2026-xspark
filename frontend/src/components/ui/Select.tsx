"use client";

import type { SelectHTMLAttributes } from "react";
import { useId } from "react";
import { IconChevronDown } from "./Icons";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** Visible caption rendered inside the control, before the value. */
  caption?: string;
  srLabel: string;
}

/**
 * Native <select> in a styled shell — keeps the platform listbox (and the
 * `combobox` role) while matching the surrounding control language.
 */
export function Select({ caption, srLabel, className = "", ...props }: SelectProps) {
  const id = useId();

  return (
    <div
      className={`group relative inline-flex h-9 items-center gap-2 rounded-lg border border-line-strong bg-surface-2 pr-8 pl-3 transition-colors duration-150 hover:border-brand/50 focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/25 ${className}`}
    >
      {caption && (
        <span aria-hidden="true" className="pointer-events-none text-[13px] whitespace-nowrap text-ink-3">
          {caption}
        </span>
      )}
      <label htmlFor={id} className="sr-only">
        {srLabel}
      </label>
      <select
        id={id}
        className="peer w-full min-w-0 cursor-pointer appearance-none bg-transparent py-1.5 text-[13px] font-medium text-ink outline-none [&>option]:bg-surface-2 [&>option]:text-ink"
        {...props}
      />
      <IconChevronDown className="pointer-events-none absolute right-2.5 h-4 w-4 text-ink-3 transition-colors group-hover:text-ink-2" />
    </div>
  );
}
