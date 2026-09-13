import type { ReactNode } from "react";
import { EmptyState } from "./States";

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** Right-align numeric columns so digits line up. */
  align?: "left" | "right";
  /** Hide below the given breakpoint to keep narrow viewports scannable. */
  hideBelow?: "sm" | "md" | "lg";
  width?: string;
  cell: (row: T, index: number) => ReactNode;
}

const HIDE: Record<string, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  emptyMessage,
  caption,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  emptyMessage: string;
  caption?: string;
}) {
  if (rows.length === 0) return <EmptyState message={emptyMessage} />;

  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="w-full min-w-full border-collapse text-left">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-line">
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                style={c.width ? { width: c.width } : undefined}
                className={`px-3 pb-2 text-[11px] font-semibold tracking-[0.06em] whitespace-nowrap text-ink-4 uppercase first:pl-5 last:pr-5 ${
                  c.align === "right" ? "text-right" : ""
                } ${c.hideBelow ? HIDE[c.hideBelow] : ""}`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={rowKey(row, i)}
              className="group border-b border-line/60 transition-colors duration-150 last:border-0 hover:bg-surface-2/50"
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`px-3 py-2.5 align-middle text-[13px] text-ink-2 first:pl-5 last:pr-5 ${
                    c.align === "right" ? "text-right" : ""
                  } ${c.hideBelow ? HIDE[c.hideBelow] : ""}`}
                >
                  {c.cell(row, i)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Rank chip used as the leading column in ranked tables. */
export function RankCell({ index }: { index: number }) {
  return (
    <span
      className={`tnum inline-flex h-6 w-6 items-center justify-center rounded-md border text-[11px] font-semibold ${
        index === 0
          ? "border-accent/30 bg-accent-soft text-accent"
          : "border-line bg-surface-2 text-ink-3"
      }`}
    >
      {index + 1}
    </span>
  );
}

/** Thin inline bar for showing a 0–1 score inside a table cell. */
export function ScoreBar({ value, tone = "brand" }: { value: number; tone?: "brand" | "accent" | "bad" }) {
  const bar = { brand: "bg-brand", accent: "bg-accent", bad: "bg-bad" }[tone];
  return (
    <span className="flex items-center justify-end gap-2">
      <span aria-hidden="true" className="hidden h-1 w-16 overflow-hidden rounded-full bg-surface-3 sm:block">
        <span
          className={`block h-full rounded-full ${bar}`}
          style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
        />
      </span>
      <span className="tnum font-medium text-ink">{value.toFixed(2)}</span>
    </span>
  );
}
