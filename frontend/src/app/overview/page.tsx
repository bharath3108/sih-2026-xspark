"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card, StatTile } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";

export default function OverviewPage() {
  const { data, loading, error, reload } = useAsync(() => api.getOverview(), []);

  if (loading) return <LoadingState label="Loading overview…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <EmptyState message="No overview data available yet." />;

  const totalSentiment = Object.values(data.sentiment_distribution).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Overview</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Event volume" value={data.volume} />
        <StatTile label="Active communities" value={data.active_communities} />
        <StatTile label="Top narratives" value={data.top_narratives.length} />
        <StatTile label="Anomalies flagged" value={data.anomalies.length} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Sentiment split">
          {totalSentiment === 0 ? (
            <EmptyState message="No sentiment signal yet." />
          ) : (
            <div className="space-y-2">
              {Object.entries(data.sentiment_distribution).map(([label, count]) => (
                <div key={label}>
                  <div className="flex justify-between text-xs text-slate-600">
                    <span className="capitalize">{label}</span>
                    <span>{count}</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-100">
                    <div
                      className={`h-2 rounded-full ${
                        label === "positive" ? "bg-emerald-500" : label === "negative" ? "bg-red-500" : "bg-slate-400"
                      }`}
                      style={{ width: `${(count / totalSentiment) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Major anomalies">
          {data.anomalies.length === 0 ? (
            <EmptyState message="No anomalies above the trend-score threshold right now." />
          ) : (
            <ul className="space-y-2">
              {data.anomalies.map((a) => (
                <li key={a.topic_id} className="flex items-center justify-between text-sm">
                  <Link href={`/topics/${a.topic_id}`} className="font-medium text-slate-800 hover:underline">
                    {a.name}
                  </Link>
                  <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">
                    {a.trend_score.toFixed(2)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Top narratives">
        {data.top_narratives.length === 0 ? (
          <EmptyState message="No narratives detected yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.top_narratives.map((t) => (
              <li key={t.topic_id} className="flex items-center justify-between py-2">
                <Link href={`/topics/${t.topic_id}`} className="text-sm font-medium text-slate-800 hover:underline">
                  {t.name}
                </Link>
                <span className="text-xs text-slate-500">trend score {t.trend_score.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
