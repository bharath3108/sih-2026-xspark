"use client";

import { useState } from "react";
import type { Data } from "plotly.js";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { PlotlyChart } from "@/components/charts/PlotlyChart";

const COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed"];

export default function TimelinePage() {
  const [selectedTopic, setSelectedTopic] = useState<string | undefined>(undefined);
  const { data, loading, error, reload } = useAsync(() => api.getTimeline(selectedTopic), [selectedTopic]);

  if (loading) return <LoadingState label="Loading timeline…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data || data.series.length === 0) return <EmptyState message="No time-series data available for this window." />;

  const volumeTraces: Data[] = data.series.map((s, i) => ({
    type: "scatter",
    mode: "lines+markers",
    name: s.name,
    x: s.points.map((p) => p.bucket_start),
    y: s.points.map((p) => p.volume),
    line: { color: COLORS[i % COLORS.length] },
  }));

  const sentimentTraces: Data[] = data.series.map((s, i) => ({
    type: "scatter",
    mode: "lines+markers",
    name: s.name,
    x: s.points.map((p) => p.bucket_start),
    y: s.points.map((p) => p.avg_sentiment),
    line: { color: COLORS[i % COLORS.length], dash: "dot" },
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Timeline</h1>
        <select
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
          value={selectedTopic ?? ""}
          onChange={(e) => setSelectedTopic(e.target.value || undefined)}
        >
          <option value="">All narratives</option>
          {data.series.map((s) => (
            <option key={s.topic_id} value={s.topic_id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <Card title="Volume over time (baseline → event → post-event)">
        <PlotlyChart data={volumeTraces} layout={{ yaxis: { title: { text: "Volume" } } }} />
      </Card>

      <Card title="Sentiment overlay (avg sentiment per bucket)">
        <PlotlyChart
          data={sentimentTraces}
          layout={{ yaxis: { title: { text: "Avg sentiment" }, range: [-1, 1] } }}
        />
      </Card>
    </div>
  );
}
