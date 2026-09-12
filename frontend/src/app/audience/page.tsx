"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card, StatTile } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";

export default function AudiencePage() {
  const [selectedTopic, setSelectedTopic] = useState<string | undefined>(undefined);

  const topicsQuery = useAsync(() => api.listTopics(), []);
  const audienceQuery = useAsync(() => api.getAudience(selectedTopic), [selectedTopic]);

  if (topicsQuery.loading || audienceQuery.loading) return <LoadingState label="Loading audience data…" />;
  if (topicsQuery.error) return <ErrorState message={topicsQuery.error} onRetry={topicsQuery.reload} />;
  if (audienceQuery.error) return <ErrorState message={audienceQuery.error} onRetry={audienceQuery.reload} />;

  const audience = audienceQuery.data;
  const topics = topicsQuery.data?.topics ?? [];

  const isLowConfidence = audience && audience.sample_size > 0 && audience.confidence < 0.5;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Audience</h1>
        <select
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
          value={selectedTopic ?? ""}
          onChange={(e) => setSelectedTopic(e.target.value || undefined)}
        >
          <option value="">All narratives (aggregate)</option>
          {topics.map((t) => (
            <option key={t.topic_id} value={t.topic_id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
        Aggregate, probabilistic demographic estimate — not an identity claim. Category shares below a minimum sample
        size or confidence should be treated as indicative only.
      </p>

      {!audience || audience.sample_size === 0 ? (
        <EmptyState message="Insufficient evidence for an audience estimate on this selection." />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="Sample size" value={audience.sample_size} />
            <StatTile label="Confidence" value={`${Math.round(audience.confidence * 100)}%`} />
            <StatTile label="Unknown share" value={`${Math.round(audience.unknown_share * 100)}%`} />
            <StatTile label="Categories" value={Object.keys(audience.categories).length} />
          </div>

          {isLowConfidence && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
              Confidence is below 50% for this selection — treat the category breakdown below as low-reliability.
            </p>
          )}

          <Card title="Category distribution">
            <div className="space-y-2">
              {Object.entries(audience.categories).map(([category, share]) => (
                <div key={category}>
                  <div className="flex justify-between text-xs text-slate-600">
                    <span className="capitalize">{category}</span>
                    <span>{Math.round(share * 100)}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-100">
                    <div className="h-2 rounded-full bg-indigo-500" style={{ width: `${share * 100}%` }} />
                  </div>
                </div>
              ))}
              <div>
                <div className="flex justify-between text-xs text-slate-500">
                  <span>unknown / insufficient evidence</span>
                  <span>{Math.round(audience.unknown_share * 100)}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-slate-400" style={{ width: `${audience.unknown_share * 100}%` }} />
                </div>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
