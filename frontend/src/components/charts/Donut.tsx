import type { ReactNode } from "react";

export interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

/**
 * Proportion ring drawn with stroke-dasharray — no chart library, scales
 * cleanly, and degrades to the centre label if every slice is zero.
 */
export function Donut({
  slices,
  size = 168,
  thickness = 16,
  centerLabel,
  centerValue,
}: {
  slices: DonutSlice[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: ReactNode;
}) {
  const total = slices.reduce((a, s) => a + s.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;

  let offset = 0;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="h-full w-full -rotate-90" aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-surface-3)"
          strokeWidth={thickness}
        />
        {total > 0 &&
          slices.map((s) => {
            const len = (s.value / total) * c;
            const dash = `${Math.max(0, len - 2)} ${c - Math.max(0, len - 2)}`;
            const el = (
              <circle
                key={s.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={thickness}
                strokeDasharray={dash}
                strokeDashoffset={-offset}
                strokeLinecap="round"
                className="transition-[stroke-dasharray] duration-500 ease-out"
              />
            );
            offset += len;
            return el;
          })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        {centerValue !== undefined && (
          <span className="tnum text-[24px] leading-none font-semibold text-ink">{centerValue}</span>
        )}
        {centerLabel && <span className="mt-1 max-w-[70%] text-[11px] leading-tight text-ink-4">{centerLabel}</span>}
      </div>
    </div>
  );
}
