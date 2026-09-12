// Ambient declarations for package entry points that ship without their own
// types and aren't covered by an @types package (which only types the
// package's default/main import).

declare module "plotly.js-cartesian-dist-min" {
  import type * as Plotly from "plotly.js";
  const plotly: typeof Plotly;
  export default plotly;
}

declare module "react-plotly.js/factory" {
  import type * as Plotly from "plotly.js";
  import type * as React from "react";
  import type { PlotParams } from "react-plotly.js";

  export default function createPlotlyComponent(
    plotly: typeof Plotly
  ): React.ComponentType<PlotParams>;
}
