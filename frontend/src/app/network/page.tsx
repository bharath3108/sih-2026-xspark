"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Badge, Card, Meter, StatCard } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { NetworkGraph, colorForCommunity } from "@/components/charts/NetworkGraph";
import { PageHeader } from "@/components/ui/PageHeader";
import { IconShare, IconTarget, IconTrend, IconUsers } from "@/components/ui/Icons";

export default function NetworkPage() {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const { data, loading, error, reload } = useAsync(() => api.getNetwork(), []);

  if (loading) return <LoadingState label="Loading network…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <EmptyState message="No network data available yet." />;

  const selectedTopologyNode = data.topology.nodes.find((n) => n.id === selectedNode);
  const communityIds = Array.from(new Set(data.topology.nodes.map((n) => n.community_id)));
  const largestCommunity = Math.max(0, ...data.communities.map((c) => c.size));

  return (
    <div className="animate-fade-rise">
      <PageHeader
        title="Network"
        description="Author graph for the current window — how clusters form, how far narratives travel, and which nodes carry them between communities."
        actions={
          <Badge tone="neutral">
            <span className="tnum font-semibold">{data.communities.length}</span> communities
          </Badge>
        }
      />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Nodes" value={data.graph_metrics.nodes.toLocaleString()} icon={<IconUsers className="h-4 w-4" />} tone="brand" />
        <StatCard label="Edges" value={data.graph_metrics.edges.toLocaleString()} icon={<IconShare className="h-4 w-4" />} tone="neutral" />
        <StatCard
          label="Density"
          value={data.graph_metrics.density.toFixed(3)}
          icon={<IconTarget className="h-4 w-4" />}
          tone="neutral"
          footer={<span>Edges / possible edges</span>}
        />
        <StatCard
          label="Propagation depth"
          value={data.propagation.depth}
          icon={<IconTrend className="h-4 w-4" />}
          tone="accent"
          footer={
            <span>
              Cross-community rate{" "}
              <span className="tnum font-medium text-ink-2">
                {Math.round(data.propagation.cross_community_rate * 100)}%
              </span>
            </span>
          }
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card
          title="Communities & propagation"
          subtitle="Node size = centrality · colour = community"
          className="xl:col-span-2"
          actions={
            selectedTopologyNode ? (
              <Badge tone="brand" dot>
                1 selected
              </Badge>
            ) : undefined
          }
        >
          {data.topology.nodes.length === 0 ? (
            <EmptyState message="No graph topology available yet." icon={<IconShare className="h-[18px] w-[18px]" />} />
          ) : (
            <div className="overflow-hidden rounded-xl border border-line bg-base/50">
              <NetworkGraph
                topology={data.topology}
                selectedNode={selectedNode}
                onNodeSelect={setSelectedNode}
              />
            </div>
          )}
          <p className="mt-2.5 text-[12px] text-ink-4">
            Click a node to inspect its community, role and centrality.
          </p>
        </Card>

        <div className="flex flex-col gap-4">
          <Card title="Selected node" subtitle={selectedTopologyNode ? undefined : "Nothing selected"}>
            {selectedTopologyNode ? (
              <dl className="space-y-2.5">
                <div>
                  <dt className="text-[11px] text-ink-4">Author hash</dt>
                  <dd className="mt-0.5 truncate font-mono text-[12px] text-ink">{selectedTopologyNode.id}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[12px] text-ink-3">Community</dt>
                  <dd className="flex items-center gap-1.5">
                    <span
                      aria-hidden="true"
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: colorForCommunity(selectedTopologyNode.community_id, communityIds) }}
                    />
                    <span className="font-mono text-[12px] text-ink">{selectedTopologyNode.community_id}</span>
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[12px] text-ink-3">Role</dt>
                  <dd>
                    <Badge tone="accent" className="capitalize">
                      {selectedTopologyNode.role}
                    </Badge>
                  </dd>
                </div>
                <div>
                  <Meter
                    label="Centrality"
                    value={selectedTopologyNode.centrality.toFixed(2)}
                    share={selectedTopologyNode.centrality}
                    tone="brand"
                  />
                </div>
              </dl>
            ) : (
              <EmptyState message="Select a node in the graph to see details." compact icon={<IconTarget className="h-[18px] w-[18px]" />} />
            )}
          </Card>

          <Card title="Communities" subtitle="Ranked by member count">
            {data.communities.length === 0 ? (
              <EmptyState message="No communities detected in this window." compact />
            ) : (
              <ul className="space-y-2">
                {[...data.communities]
                  .sort((a, b) => b.size - a.size)
                  .map((c) => (
                    <li key={c.community_id}>
                      <Meter
                        label={c.community_id}
                        value={`${c.size}`}
                        share={largestCommunity ? c.size / largestCommunity : 0}
                        tone="brand"
                      />
                    </li>
                  ))}
              </ul>
            )}
          </Card>

          <Card title="Key propagation nodes" subtitle="Carry narratives between communities">
            {data.propagation.key_nodes.length === 0 ? (
              <EmptyState message="No key propagation nodes identified yet." compact />
            ) : (
              <ul className="space-y-1.5">
                {data.propagation.key_nodes.map((n) => {
                  const node = data.topology.nodes.find((t) => t.id === n);
                  const active = selectedNode === n;
                  return (
                    <li key={n}>
                      <button
                        type="button"
                        onClick={() => setSelectedNode(n)}
                        className={`flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left transition-colors duration-150 ${
                          active
                            ? "border-brand/40 bg-brand-soft"
                            : "border-line bg-surface-2/50 hover:border-line-strong hover:bg-surface-2"
                        }`}
                      >
                        {node && (
                          <span
                            aria-hidden="true"
                            className="h-2 w-2 shrink-0 rounded-full"
                            style={{ backgroundColor: colorForCommunity(node.community_id, communityIds) }}
                          />
                        )}
                        <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-ink-2">{n}</span>
                        {node && <span className="tnum shrink-0 text-[11px] text-ink-4">{node.centrality.toFixed(2)}</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
