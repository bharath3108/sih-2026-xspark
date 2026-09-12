"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card, StatTile } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { NetworkGraph } from "@/components/charts/NetworkGraph";

export default function NetworkPage() {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const { data, loading, error, reload } = useAsync(() => api.getNetwork(), []);

  if (loading) return <LoadingState label="Loading network…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <EmptyState message="No network data available yet." />;

  const selectedTopologyNode = data.topology.nodes.find((n) => n.id === selectedNode);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Network</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Nodes" value={data.graph_metrics.nodes} />
        <StatTile label="Edges" value={data.graph_metrics.edges} />
        <StatTile label="Density" value={data.graph_metrics.density.toFixed(3)} />
        <StatTile label="Propagation depth" value={data.propagation.depth} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Communities & propagation" className="lg:col-span-2">
          {data.topology.nodes.length === 0 ? (
            <EmptyState message="No graph topology available yet." />
          ) : (
            <NetworkGraph topology={data.topology} onNodeSelect={setSelectedNode} />
          )}
          <p className="mt-2 text-xs text-slate-500">Click a node to inspect it. Node size = centrality, color = community.</p>
        </Card>

        <div className="space-y-4">
          <Card title="Communities">
            <ul className="space-y-2 text-sm">
              {data.communities.map((c) => (
                <li key={c.community_id} className="flex justify-between">
                  <span>{c.community_id}</span>
                  <span className="text-xs text-slate-500">{c.size} members</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Selected node">
            {selectedTopologyNode ? (
              <div className="space-y-1 text-sm">
                <p>
                  <span className="text-slate-500">Author hash:</span> {selectedTopologyNode.id}
                </p>
                <p>
                  <span className="text-slate-500">Community:</span> {selectedTopologyNode.community_id}
                </p>
                <p>
                  <span className="text-slate-500">Role:</span> {selectedTopologyNode.role}
                </p>
                <p>
                  <span className="text-slate-500">Centrality:</span> {selectedTopologyNode.centrality.toFixed(2)}
                </p>
              </div>
            ) : (
              <EmptyState message="Select a node in the graph to see details." />
            )}
          </Card>

          <Card title="Key propagation nodes">
            <ul className="space-y-1 text-sm">
              {data.propagation.key_nodes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
