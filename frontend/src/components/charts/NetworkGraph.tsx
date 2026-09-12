"use client";

import dynamic from "next/dynamic";
import type { Topology } from "@/lib/types";
import type { ComponentProps } from "react";
import type CytoscapeComponentType from "react-cytoscapejs";

// Cytoscape renders to a canvas/DOM node and must not run during SSR.
const CytoscapeComponent = dynamic(() => import("react-cytoscapejs"), {
  ssr: false,
  loading: () => <div className="h-[420px] animate-pulse rounded-lg bg-slate-100" />,
}) as unknown as typeof CytoscapeComponentType;

const COMMUNITY_COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2"];

function colorForCommunity(communityId: string, communityIds: string[]): string {
  const idx = communityIds.indexOf(communityId);
  return COMMUNITY_COLORS[idx % COMMUNITY_COLORS.length];
}

export function NetworkGraph({
  topology,
  onNodeSelect,
}: {
  topology: Topology;
  onNodeSelect?: (nodeId: string) => void;
}) {
  const communityIds = Array.from(new Set(topology.nodes.map((n) => n.community_id)));

  const elements: ComponentProps<typeof CytoscapeComponentType>["elements"] = [
    ...topology.nodes.map((n) => ({
      data: { id: n.id, label: n.id, role: n.role, community: n.community_id },
      style: {
        "background-color": colorForCommunity(n.community_id, communityIds),
        width: 24 + n.centrality * 40,
        height: 24 + n.centrality * 40,
      },
    })),
    ...topology.edges.map((e, i) => ({
      data: { id: `e${i}`, source: e.source, target: e.target, weight: e.weight },
    })),
  ];

  return (
    <CytoscapeComponent
      elements={elements}
      style={{ width: "100%", height: 420 }}
      layout={{ name: "cose", animate: false, padding: 30 }}
      stylesheet={[
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: "#1e293b",
            "font-size": 10,
            "text-valign": "bottom",
            "text-margin-y": 4,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#cbd5e1",
            "target-arrow-color": "#cbd5e1",
            "target-arrow-shape": "triangle",
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
