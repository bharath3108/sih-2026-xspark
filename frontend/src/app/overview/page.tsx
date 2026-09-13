"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Badge, Card, Meter, StatCard } from "@/components/ui/Card";
import { Column, DataTable, RankCell, ScoreBar } from "@/components/ui/DataTable";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button, IconButton } from "@/components/ui/Button";
import {
  IconAlert,
  IconArrowUpRight,
  IconLayers,
  IconPulse,
  IconRefresh,
  IconShare,
} from "@/components/ui/Icons";
import type { OverviewResponse } from "@/lib/types";

const SENTIMENT_TONE = {
  positive: "ok",
  negative: "bad",
  neutral: "neutral",
} as const;

type Narrative = OverviewResponse["top_narratives"][number];

export default function OverviewPage() {
  const { data, loading, error, reload } = useAsync(() => api.getOverview(), []);

  if (loading) return <LoadingState label="Loading overview…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <EmptyState message="No overview data available yet." />;

  const sentimentEntries = Object.entries(data.sentiment_distribution);
  const totalSentiment = sentimentEntries.reduce((a, [, b]) => a + b, 0);
  const dominant = sentimentEntries.sort((a, b) => b[1] - a[1])[0];

  const narrativeColumns: Column<Narrative>[] = [
    {
      key: "rank",
      header: "#",
      width: "48px",
      cell: (_row, i) => <RankCell index={i} />,
    },
    {
      key: "name",
      header: "Narrative",
      cell: (row) => (
        <Link
          href={`/topics/${row.topic_id}`}
          className="font-medium text-ink transition-colors hover:text-brand"
        >
          {row.name}
        </Link>
      ),
    },
    {
      key: "id",
      header: "Topic ID",
      hideBelow: "md",
      cell: (row) => <span className="font-mono text-[12px] text-ink-4">{row.topic_id}</span>,
    },
    {
      key: "trend",
      header: "Trend score",
      align: "right",
      width: "140px",
      cell: (row) => <ScoreBar value={row.trend_score} tone={row.trend_score >= 0.85 ? "accent" : "brand"} />,
    },
  ];

  return (
    <div className="animate-fade-rise">
      <PageHeader
        title="Overview"
        description="Signal across the current collection window — volume, sentiment balance and anything crossing the anomaly threshold."
        actions={
          <Button variant="secondary" onClick={reload} icon={<IconRefresh className="h-4 w-4" />}>
            Refresh
          </Button>
        }
      />

      {/* KPI row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Event volume"
          value={data.volume.toLocaleString()}
          icon={<IconPulse className="h-4 w-4" />}
          tone="brand"
          footer={
            dominant ? (
              <span>
                Dominant sentiment <span className="font-medium text-ink-2 capitalize">{dominant[0]}</span>
                {totalSentiment > 0 && (
                  <span className="tnum text-ink-4"> · {Math.round((dominant[1] / totalSentiment) * 100)}%</span>
                )}
              </span>
            ) : (
              <span className="text-ink-4">No sentiment signal</span>
            )
          }
        />
        <StatCard
          label="Active communities"
          value={data.active_communities}
          icon={<IconShare className="h-4 w-4" />}
          tone="neutral"
          footer={
            <Link href="/network" className="inline-flex items-center gap-1 text-ink-3 transition-colors hover:text-brand">
              Inspect topology <IconArrowUpRight className="h-3 w-3" />
            </Link>
          }
        />
        <StatCard
          label="Top narratives"
          value={data.top_narratives.length}
          icon={<IconLayers className="h-4 w-4" />}
          tone="neutral"
          footer={
            <Link href="/topics" className="inline-flex items-center gap-1 text-ink-3 transition-colors hover:text-brand">
              Browse narratives <IconArrowUpRight className="h-3 w-3" />
            </Link>
          }
        />
        <StatCard
          label="Anomalies flagged"
          value={data.anomalies.length}
          icon={<IconAlert className="h-4 w-4" />}
          tone={data.anomalies.length > 0 ? "bad" : "ok"}
          footer={
            data.anomalies.length > 0 ? (
              <span className="text-bad/90">Above trend-score threshold</span>
            ) : (
              <span className="text-ink-4">Nothing above threshold</span>
            )
          }
        />
      </div>

      {/* Primary analytics */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Card
          title="Sentiment split"
          subtitle={totalSentiment > 0 ? `${totalSentiment.toLocaleString()} classified events` : undefined}
          className="lg:col-span-2"
        >
          {totalSentiment === 0 ? (
            <EmptyState message="No sentiment signal yet." />
          ) : (
            <div className="space-y-3.5">
              {sentimentEntries.map(([label, count]) => (
                <Meter
                  key={label}
                  label={label}
                  value={
                    <>
                      {count.toLocaleString()}
                      <span className="ml-1.5 font-normal text-ink-4">
                        {Math.round((count / totalSentiment) * 100)}%
                      </span>
                    </>
                  }
                  share={count / totalSentiment}
                  tone={SENTIMENT_TONE[label as keyof typeof SENTIMENT_TONE] ?? "neutral"}
                />
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Major anomalies"
          subtitle="Narratives crossing the trend-score threshold"
          className="lg:col-span-3"
          actions={
            data.anomalies.length > 0 ? (
              <Badge tone="bad" dot>
                {data.anomalies.length} flagged
              </Badge>
            ) : undefined
          }
        >
          {data.anomalies.length === 0 ? (
            <EmptyState
              message="No anomalies above the trend-score threshold right now."
              icon={<IconAlert className="h-[18px] w-[18px]" />}
            />
          ) : (
            <ul className="space-y-2">
              {data.anomalies.map((a) => (
                <li key={a.topic_id}>
                  <Link
                    href={`/topics/${a.topic_id}`}
                    className="group flex items-center gap-3 rounded-xl border border-bad/20 bg-bad-soft/50 px-3.5 py-3 transition-colors duration-150 hover:border-bad/35 hover:bg-bad-soft"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-bad-soft text-bad">
                      <IconAlert className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[14px] font-medium text-ink">{a.name}</span>
                      <span className="block truncate text-[12px] text-ink-3">{a.reason}</span>
                    </span>
                    <span className="tnum shrink-0 text-[15px] font-semibold text-bad">
                      {a.trend_score.toFixed(2)}
                    </span>
                    <IconArrowUpRight className="h-4 w-4 shrink-0 text-ink-4 transition-colors group-hover:text-bad" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Detail table */}
      <div className="mt-4">
        <Card
          title="Top narratives"
          subtitle="Ranked by trend score across the window"
          bodyClassName="px-0 pb-0"
          actions={
            <Link href="/topics">
              <IconButton label="Open narratives" variant="outline" size="sm">
                <IconArrowUpRight className="h-4 w-4" />
              </IconButton>
            </Link>
          }
        >
          {data.top_narratives.length === 0 ? (
            <div className="px-5 pb-5">
              <EmptyState message="No narratives detected yet." icon={<IconLayers className="h-[18px] w-[18px]" />} />
            </div>
          ) : (
            <DataTable
              caption="Top narratives ranked by trend score"
              columns={narrativeColumns}
              rows={data.top_narratives}
              rowKey={(r) => r.topic_id}
              emptyMessage="No narratives detected yet."
            />
          )}
        </Card>
      </div>
    </div>
  );
}
