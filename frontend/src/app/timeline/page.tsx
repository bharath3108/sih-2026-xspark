"use client";

import { useState } from "react";
import type { Data } from "plotly.js";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card, StatCard } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { ChartLegend, PlotlyChart, SERIES } from "@/components/charts/PlotlyChart";
import { PageHeader, FilterBar } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Select";
import { IconClock, IconPulse, IconTrend, IconLayers } from "@/components/ui/Icons";

/** rgba() version of a series colour, for area fills. */
function fill(hex: string, alpha: number) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

export default function TimelinePage() {
  const [selectedTopic, setSelectedTopic] = useState<string | undefined>(undefined);
  const { data, loading, error, reload } = useAsync(() => api.getTimeline(selectedTopic), [selectedTopic]);

  if (loading) return <LoadingState label="Loading timeline…" variant="chart" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data || data.series.length === 0)
    return <EmptyState message="No time-series data available for this window." />;

  const allPoints = data.series.flatMap((s) => s.points);
  const totalVolume = allPoints.reduce((a, p) => a + p.volume, 0);
  const peak = allPoints.reduce((max, p) => (p.volume > max.volume ? p : max), allPoints[0]);
  const avgSentiment = allPoints.length
    ? allPoints.reduce((a, p) => a + p.avg_sentiment, 0) / allPoints.length
    : 0;
  const buckets = new Set(allPoints.map((p) => p.bucket_start)).size;

  const single = data.series.length === 1;

  const volumeTraces: Data[] = data.series.map((s, i) => ({
    type: "scatter",
    mode: "lines",
    name: s.name,
    x: s.points.map((p) => p.bucket_start),
    y: s.points.map((p) => p.volume),
    line: { color: SERIES[i % SERIES.length], width: 2, shape: "spline", smoothing: 0.6 },
    // A filled area reads well for one series; stacked fills would muddle many.
    fill: single ? "tozeroy" : "none",
    fillcolor: fill(SERIES[i % SERIES.length], 0.13),
    hovertemplate: "%{y:,} events<extra>%{fullData.name}</extra>",
  }));

  const sentimentTraces: Data[] = data.series.map((s, i) => ({
    type: "scatter",
    mode: "lines+markers",
    name: s.name,
    x: s.points.map((p) => p.bucket_start),
    y: s.points.map((p) => p.avg_sentiment),
    line: { color: SERIES[i % SERIES.length], width: 1.75, dash: "dot" },
    marker: { size: 4 },
    hovertemplate: "%{y:.2f}<extra>%{fullData.name}</extra>",
  }));

  const legend = data.series.map((s, i) => ({
    label: s.name,
    color: SERIES[i % SERIES.length],
    value: `${s.points.reduce((a, p) => a + p.volume, 0).toLocaleString()}`,
  }));

  return (
    <div className="animate-fade-rise">
      <PageHeader
        title="Timeline"
        description="How each narrative moved through the collection window — baseline, event spike, then post-event decay."
      >
        <FilterBar note={`${buckets} time buckets`}>
          <Select
            caption="Narrative"
            srLabel="Filter timeline by narrative"
            value={selectedTopic ?? ""}
            onChange={(e) => setSelectedTopic(e.target.value || undefined)}
          >
            <option value="">All narratives</option>
            {data.series.map((s) => (
              <option key={s.topic_id} value={s.topic_id}>
                {s.name}
              </option>
            ))}
          </Select>
        </FilterBar>
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label="Total volume"
          value={totalVolume.toLocaleString()}
          icon={<IconPulse className="h-4 w-4" />}
          tone="brand"
        />
        <StatCard
          label="Peak bucket"
          value={peak ? peak.volume.toLocaleString() : "—"}
          icon={<IconTrend className="h-4 w-4" />}
          tone="accent"
          footer={
            peak ? (
              <span className="tnum">
                {new Date(peak.bucket_start).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            ) : undefined
          }
        />
        <StatCard
          label="Avg sentiment"
          value={avgSentiment.toFixed(2)}
          icon={<IconGaugeSentiment value={avgSentiment} />}
          tone={avgSentiment > 0.05 ? "ok" : avgSentiment < -0.05 ? "bad" : "neutral"}
          footer={<span>Scale −1 to +1</span>}
        />
        <StatCard
          label="Series tracked"
          value={data.series.length}
          icon={<IconLayers className="h-4 w-4" />}
          footer={
            <span className="inline-flex items-center gap-1">
              <IconClock className="h-3 w-3" /> {buckets} buckets
            </span>
          }
        />
      </div>

      <div className="mt-4 space-y-4">
        <Card
          title="Volume over time"
          subtitle="Events per bucket, baseline through post-event"
          actions={<ChartLegend items={legend} />}
        >
          <PlotlyChart
            data={volumeTraces}
            height={320}
            layout={{ yaxis: { title: { text: "Volume" }, rangemode: "tozero" } }}
          />
        </Card>

        <Card
          title="Sentiment overlay"
          subtitle="Average sentiment per bucket, −1 (negative) to +1 (positive)"
          actions={<ChartLegend items={data.series.map((s, i) => ({ label: s.name, color: SERIES[i % SERIES.length] }))} />}
        >
          <PlotlyChart
            data={sentimentTraces}
            height={280}
            layout={{
              yaxis: { title: { text: "Avg sentiment" }, range: [-1, 1], zeroline: true },
            }}
          />
        </Card>
      </div>
    </div>
  );
}

/** Small inline glyph whose direction tracks the sentiment sign. */
function IconGaugeSentiment({ value }: { value: number }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" className="h-4 w-4" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      {value > 0.05 ? (
        <path d="M8.5 14c1 1.4 2.2 2 3.5 2s2.5-.6 3.5-2" />
      ) : value < -0.05 ? (
        <path d="M8.5 16c1-1.4 2.2-2 3.5-2s2.5.6 3.5 2" />
      ) : (
        <path d="M8.5 15h7" />
      )}
      <path d="M9.5 9.5h.01M14.5 9.5h.01" />
    </svg>
  );
}
