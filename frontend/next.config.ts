import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Playwright (and some local network setups) load the dev server via
  // 127.0.0.1 rather than localhost; Next 16 blocks cross-origin dev
  // requests (HMR, RSC payloads) by default unless the origin is allowlisted.
  allowedDevOrigins: ["127.0.0.1", "localhost"],

  // This app is a subdirectory of a mixed Python/JS repo. Left to itself, Next
  // walks up past `frontend/` looking for a workspace root and traces server
  // bundles from there, which drags the whole checkout into every serverless
  // function. Pin the root to this directory.
  outputFileTracingRoot: path.resolve(__dirname),

  // Plotly, Cytoscape and maplibre are ~110MB of production dependencies that
  // only ever run in the browser (loaded via next/dynamic with ssr:false), so
  // they must not be copied into server function bundles.
  outputFileTracingExcludes: {
    "*": [
      "node_modules/plotly.js/**",
      "node_modules/plotly.js-cartesian-dist-min/**",
      "node_modules/react-plotly.js/**",
      "node_modules/maplibre-gl/**",
      "node_modules/@maplibre/**",
      "node_modules/cytoscape/**",
      "node_modules/react-cytoscapejs/**",
    ],
  },
};

export default nextConfig;
