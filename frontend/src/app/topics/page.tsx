"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Badge } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sparkline } from "@/components/charts/Sparkline";
import { IconArrowUpRight, IconLayers } from "@/components/ui/Icons";
import type { Topic } from "@/lib/types";

function trendTone(score: number) {
  return score >= 0.85 ? "bad" : score >= 0.6 ? "warn" : "neutral";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="truncate text-[11px] text-ink-4">{label}</p>
      <p className="tnum mt-0.5 truncate text-[14px] font-semibold text-ink">{value}</p>
    </div>
  );
}

function NarrativeCard({ topic }: { topic: Topic }) {
  const score = topic.metrics.trend_score;
  const tone = trendTone(score);
  const sparkColor = score >= 0.85 ? "#ff4d5e" : score >= 0.6 ? "#f5a524" : "#7c5cff";

  return (
    <Link
      href={`/topics/${topic.topic_id}`}
      className="surface-card group relative flex flex-col overflow-hidden rounded-card border border-line bg-surface shadow-card transition-[border-color,background-color,transform] duration-200 hover:-translate-y-0.5 hover:border-brand/40 hover:bg-surface-2/50"
    >
      <div className="flex items-start justify-between gap-3 px-5 pt-4">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] leading-6 font-semibold text-ink transition-colors group-hover:text-brand">
            {topic.name}
          </h3>
          <p className="mt-0.5 truncate font-mono text-[11px] text-ink-4">{topic.topic_id}</p>
        </div>
        <Badge tone={tone} className="shrink-0">
          trend <span className="tnum font-semibold">{score.toFixed(2)}</span>
        </Badge>
      </div>

      {topic.timeline.length > 1 && (
        <div className="mt-3 px-1">
          <Sparkline values={topic.timeline.map((p) => p.volume)} color={sparkColor} height={40} />
        </div>
      )}

      <div className="mt-auto grid grid-cols-3 gap-3 border-t border-line px-5 py-3.5">
        <Stat label="Posts" value={topic.metrics.volume.toLocaleString()} />
        <Stat label="Authors" value={topic.metrics.unique_authors.toLocaleString()} />
        <Stat label="Engagement" value={topic.metrics.engagement.toLocaleString()} />
      </div>

      <span
        aria-hidden="true"
        className="absolute top-4 right-4 translate-x-1 opacity-0 transition-all duration-200 group-hover:translate-x-0 group-hover:opacity-100"
      >
        <IconArrowUpRight className="h-4 w-4 text-brand" />
      </span>
    </Link>
  );
}

export default function TopicsPage() {
  const { data, loading, error, reload } = useAsync(() => api.listTopics(), []);

  if (loading) return <LoadingState label="Loading narratives…" variant="list" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data || data.topics.length === 0)
    return (
      <div className="animate-fade-rise">
        <PageHeader title="Narratives" description="Detected narratives ranked by trend score." />
        <EmptyState message="No narratives detected yet." icon={<IconLayers className="h-[18px] w-[18px]" />} />
      </div>
    );

  const sorted = [...data.topics].sort((a, b) => b.metrics.trend_score - a.metrics.trend_score);

  return (
    <div className="animate-fade-rise">
      <PageHeader
        title="Narratives"
        description="Every narrative detected in the current window, ordered by trend score. Open one to see its evidence, sentiment and community spread."
        actions={
          <Badge tone="neutral">
            <span className="tnum font-semibold">{sorted.length}</span> detected
          </Badge>
        }
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {sorted.map((t) => (
          <NarrativeCard key={t.topic_id} topic={t} />
        ))}
      </div>
    </div>
  );
}
