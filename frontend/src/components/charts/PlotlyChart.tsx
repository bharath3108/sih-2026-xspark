"use client";

import dynamic from "next/dynamic";
import type { Data, Layout } from "plotly.js";

// Plotly touches `window`/`document` at import time, so it must never run
// during SSR. We also use the cartesian-only build (no maplibre-gl) since we
// only render line/bar time-series charts here.
const Plot = dynamic(
  async () => {
    const createPlotlyComponent = (await import("react-plotly.js/factory")).default;
    const Plotly = (await import("plotly.js-cartesian-dist-min")).default;
    return createPlotlyComponent(Plotly);
  },
  { ssr: false, loading: () => <div className="skeleton h-72 w-full rounded-xl" /> }
);

/** Series palette — mirrors --color-series-* so charts match the rest of the UI. */
export const SERIES = ["#7c5cff", "#ff6b2c", "#38bdf8", "#2fd98a", "#f5a524", "#f472b6"];

const INK_3 = "#71748a";
const GRID = "rgba(255,255,255,0.055)";
const ZERO = "rgba(255,255,255,0.14)";

const AXIS = {
  gridcolor: GRID,
  zerolinecolor: ZERO,
  linecolor: "rgba(255,255,255,0.09)",
  tickfont: { size: 11, color: INK_3 },
  title: { font: { size: 11, color: INK_3 } },
  automargin: true,
} as const;

export function PlotlyChart({
  data,
  layout,
  height = 300,
}: {
  data: Data[];
  layout?: Partial<Layout>;
  height?: number;
}) {
  return (
    <Plot
      data={data}
      layout={{
        autosize: true,
        height,
        margin: { l: 46, r: 12, t: 8, b: 36 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { size: 11, color: INK_3, family: "var(--font-geist-sans), system-ui, sans-serif" },
        colorway: SERIES,
        hoverlabel: {
          bgcolor: "#1a1a28",
          bordercolor: "rgba(255,255,255,0.12)",
          font: { color: "#f3f4f8", size: 12 },
        },
        hovermode: "x unified",
        showlegend: false,
        ...layout,
        xaxis: { ...AXIS, ...layout?.xaxis },
        yaxis: { ...AXIS, ...layout?.yaxis },
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}

/** Shared legend so series colour meaning stays consistent across charts. */
export function ChartLegend({
  items,
}: {
  items: { label: string; color: string; value?: string }[];
}) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5 text-[12px]">
          <span
            aria-hidden="true"
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: item.color }}
          />
          <span className="text-ink-3">{item.label}</span>
          {item.value && <span className="tnum font-medium text-ink-2">{item.value}</span>}
        </li>
      ))}
    </ul>
  );
}
