"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";

export default function TopicsPage() {
  const { data, loading, error, reload } = useAsync(() => api.listTopics(), []);

  if (loading) return <LoadingState label="Loading narratives…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data || data.topics.length === 0) return <EmptyState message="No narratives detected yet." />;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Narratives</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {data.topics.map((t) => (
          <Link key={t.topic_id} href={`/topics/${t.topic_id}`}>
            <Card className="transition hover:border-slate-400">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-slate-900">{t.name}</p>
                  <p className="text-xs text-slate-500">{t.topic_id}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                  trend {t.metrics.trend_score.toFixed(2)}
                </span>
              </div>
              <div className="mt-3 flex gap-4 text-xs text-slate-500">
                <span>{t.metrics.volume} posts</span>
                <span>{t.metrics.unique_authors} authors</span>
                <span>{t.metrics.engagement} engagement</span>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
