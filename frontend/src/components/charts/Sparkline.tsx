import { useId } from "react";

/**
 * Inline trend glyph for card headers and table cells. Pure SVG — no chart
 * library, so it stays cheap when many render at once.
 */
export function Sparkline({
  values,
  color = "#7c5cff",
  height = 36,
  className = "",
  label,
}: {
  values: number[];
  color?: string;
  height?: number;
  className?: string;
  label?: string;
}) {
  const gradientId = useId();
  if (values.length < 2) return null;

  const w = 100;
  const h = height;
  const pad = 2;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const flat = max === min;

  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    // A flat series has no meaningful shape — draw it down the middle rather
    // than pinning it to an arbitrary edge.
    const y = flat ? h / 2 : h - pad - ((v - min) / (max - min)) * (h - pad * 2);
    return [x, y] as const;
  });

  const line = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const area = `${line} L${w},${h} L0,${h} Z`;
  const [lastX, lastY] = pts[pts.length - 1];

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className={`w-full ${className}`}
      style={{ height }}
      role={label ? "img" : "presentation"}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.28} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={lastX} cy={lastY} r={2} fill={color} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
