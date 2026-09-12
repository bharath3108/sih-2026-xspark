"use client";

import { use } from "react";
import Link from "next/link";
import type { Data } from "plotly.js";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card, StatTile } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { PlotlyChart } from "@/components/charts/PlotlyChart";

export default function TopicDetailPage({ params }: { params: Promise<{ topicId: string }> }) {
  const { topicId } = use(params);

  const { data, loading, error, reload } = useAsync(async () => {
    const [topic, network] = await Promise.all([api.getTopic(topicId), api.getNetwork()]);
    return { topic, network };
  }, [topicId]);

  if (loading) return <LoadingState label="Loading narrative…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <EmptyState message="Narrative not found." />;

  const { topic, network } = data;

  const affectedCommunityIds = new Set(
    topic.evidence_events
      .map((e) => network.topology.nodes.find((n) => n.id === e.author_id_hash)?.community_id)
      .filter((c): c is string => Boolean(c))
  );

  const evolutionTrace: Data = {
    type: "scatter",
    mode: "lines+markers",
    name: "volume",
    x: topic.timeline.map((p) => p.bucket_start),
    y: topic.timeline.map((p) => p.volume),
    line: { color: "#2563eb" },
  };

  return (
    <div className="space-y-6">
      <div>
        <Link href="/topics" className="text-xs text-slate-500 hover:underline">
          ← Narratives
        </Link>
        <h1 className="mt-1 text-xl font-semibold text-slate-900">{topic.name}</h1>
        <p className="text-xs text-slate-500">{topic.topic_id}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Trend score" value={topic.metrics.trend_score.toFixed(2)} />
        <StatTile label="Novelty" value={topic.metrics.novelty.toFixed(2)} />
        <StatTile label="Cross-community spread" value={topic.metrics.cross_community_spread.toFixed(2)} />
        <StatTile label="Affected communities" value={affectedCommunityIds.size} />
      </div>

      <Card title="Topic evolution">
        {topic.timeline.length === 0 ? (
          <EmptyState message="No timeline points recorded for this narrative." />
        ) : (
          <PlotlyChart data={[evolutionTrace]} />
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Sentiment / emotion / stance">
          {topic.nlp_outputs.length === 0 ? (
            <EmptyState message="No NLP signal attached to this narrative's evidence yet." />
          ) : (
            <ul className="space-y-2 text-sm">
              {topic.nlp_outputs.map((n) => (
                <li key={n.event_id} className="flex flex-wrap gap-2 border-b border-slate-100 pb-2 last:border-0">
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs capitalize">
                    {n.sentiment.label} ({Math.round(n.sentiment.confidence * 100)}%)
                  </span>
                  {n.emotion && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs capitalize">{n.emotion.label}</span>
                  )}
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs capitalize">stance: {n.stance.label}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Affected communities">
          {affectedCommunityIds.size === 0 ? (
            <EmptyState message="No community linkage found for this narrative's evidence yet." />
          ) : (
            <ul className="space-y-1 text-sm">
              {[...affectedCommunityIds].map((cid) => {
                const community = network.communities.find((c) => c.community_id === cid);
                return (
                  <li key={cid} className="flex justify-between">
                    <span>{cid}</span>
                    <span className="text-xs text-slate-500">{community?.size ?? "?"} members</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Evidence / examples">
        {topic.evidence_events.length === 0 ? (
          <EmptyState message="No evidence events on record for this narrative." />
        ) : (
          <ul className="space-y-3">
            {topic.evidence_events.map((e) => (
              <li key={e.event_id} className="border-b border-slate-100 pb-2 text-sm last:border-0">
                <p className="text-slate-800">{e.text}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {e.source} · {new Date(e.timestamp_utc).toLocaleString()} · {e.engagement.likes} likes ·{" "}
                  {e.engagement.shares} shares
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
