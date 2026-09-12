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
  { ssr: false, loading: () => <div className="h-72 animate-pulse rounded-lg bg-slate-100" /> }
);

export function PlotlyChart({
  data,
  layout,
  height = 320,
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
        margin: { l: 48, r: 16, t: 24, b: 40 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { size: 12, color: "#334155" },
        legend: { orientation: "h", y: -0.2 },
        ...layout,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
