"use client";

import dynamic from "next/dynamic";
import type { Topology } from "@/lib/types";
import type { ComponentProps } from "react";
import type CytoscapeComponentType from "react-cytoscapejs";

// Cytoscape renders to a canvas/DOM node and must not run during SSR.
const CytoscapeComponent = dynamic(() => import("react-cytoscapejs"), {
  ssr: false,
  loading: () => <div className="skeleton h-[420px] w-full rounded-xl" />,
}) as unknown as typeof CytoscapeComponentType;

/** Matches --color-series-* and the chart palette. */
export const COMMUNITY_COLORS = ["#7c5cff", "#ff6b2c", "#38bdf8", "#2fd98a", "#f5a524", "#f472b6"];

export function colorForCommunity(communityId: string, communityIds: string[]): string {
  const idx = communityIds.indexOf(communityId);
  return COMMUNITY_COLORS[idx % COMMUNITY_COLORS.length];
}

export function NetworkGraph({
  topology,
  selectedNode,
  onNodeSelect,
}: {
  topology: Topology;
  selectedNode?: string | null;
  onNodeSelect?: (nodeId: string) => void;
}) {
  const communityIds = Array.from(new Set(topology.nodes.map((n) => n.community_id)));
  // Author hashes are unreadable once the graph is dense — drop them and let
  // the node inspector carry identity instead.
  const showLabels = topology.nodes.length <= 40;

  const elements: ComponentProps<typeof CytoscapeComponentType>["elements"] = [
    ...topology.nodes.map((n) => {
      const color = colorForCommunity(n.community_id, communityIds);
      const selected = selectedNode === n.id;
      return {
        data: { id: n.id, label: n.id, role: n.role, community: n.community_id },
        style: {
          "background-color": color,
          "border-color": selected ? "#ffffff" : color,
          "border-width": selected ? 2.5 : 0,
          "border-opacity": selected ? 0.9 : 0,
          width: 18 + n.centrality * 38,
          height: 18 + n.centrality * 38,
        },
      };
    }),
    ...topology.edges.map((e, i) => ({
      data: { id: `e${i}`, source: e.source, target: e.target, weight: e.weight },
    })),
  ];

  return (
    <CytoscapeComponent
      elements={elements}
      style={{ width: "100%", height: 420 }}
      // cose is force-directed and O(n²)-ish per iteration; at a few hundred
      // authors the default 1000 iterations blocks the main thread for seconds.
      // Fewer iterations still separates the communities legibly.
      layout={{
        name: "cose",
        animate: false,
        padding: 28,
        randomize: false,
        numIter: topology.nodes.length > 120 ? 200 : 1000,
      }}
      stylesheet={[
        {
          selector: "node",
          style: {
            label: showLabels ? "data(label)" : "",
            color: "#71748a",
            "font-size": 9,
            "font-family": "var(--font-geist-sans), system-ui, sans-serif",
            "text-valign": "bottom",
            "text-margin-y": 5,
            "overlay-opacity": 0,
            "transition-property": "border-width, border-opacity",
            "transition-duration": 150,
          },
        },
        {
          selector: "node:active",
          style: { "overlay-opacity": 0.12, "overlay-color": "#ffffff" },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "rgba(255,255,255,0.11)",
            "target-arrow-color": "rgba(255,255,255,0.16)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.65,
            "curve-style": "bezier",
          },
        },
      ]}
      cy={(cy) => {
        cy.off("tap", "node");
        cy.on("tap", "node", (evt) => onNodeSelect?.(evt.target.id()));
      }}
    />
  );
}
