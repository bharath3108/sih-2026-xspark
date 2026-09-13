"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card, Meter, StatCard } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { PageHeader, FilterBar } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Select";
import { Donut, type DonutSlice } from "@/components/charts/Donut";
import { SERIES } from "@/components/charts/PlotlyChart";
import { IconAlert, IconShield, IconTarget, IconUsers } from "@/components/ui/Icons";

/** Non-blocking notice strip. */
function Callout({
  tone,
  icon,
  children,
}: {
  tone: "warn" | "bad";
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  const styles =
    tone === "warn"
      ? "border-warn/25 bg-warn-soft text-warn"
      : "border-bad/25 bg-bad-soft text-bad";
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border px-3.5 py-3 ${styles}`}>
      <span className="mt-px shrink-0">{icon}</span>
      <p className="text-[12px] leading-5">{children}</p>
    </div>
  );
}

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

  const categoryEntries = audience ? Object.entries(audience.categories) : [];
  const slices: DonutSlice[] = [
    ...categoryEntries.map(([label, share], i) => ({
      label,
      value: share,
      color: SERIES[i % SERIES.length],
    })),
    ...(audience && audience.unknown_share > 0
      ? [{ label: "unknown", value: audience.unknown_share, color: "#4c4f63" }]
      : []),
  ];

  const topCategory = categoryEntries.sort((a, b) => b[1] - a[1])[0];

  return (
    <div className="animate-fade-rise">
      <PageHeader
        title="Audience"
        description="Aggregate composition of the authors behind a narrative, estimated from observable signals."
      >
        <FilterBar>
          <Select
            caption="Scope"
            srLabel="Filter audience estimate by narrative"
            value={selectedTopic ?? ""}
            onChange={(e) => setSelectedTopic(e.target.value || undefined)}
          >
            <option value="">All narratives (aggregate)</option>
            {topics.map((t) => (
              <option key={t.topic_id} value={t.topic_id}>
                {t.name}
              </option>
            ))}
          </Select>
        </FilterBar>
      </PageHeader>

      <div className="space-y-4">
        <Callout tone="warn" icon={<IconShield className="h-4 w-4" />}>
          Aggregate, probabilistic demographic estimate — not an identity claim. Category shares below a minimum sample
          size or confidence should be treated as indicative only.
        </Callout>

        {!audience || audience.sample_size === 0 ? (
          <EmptyState
            message="Insufficient evidence for an audience estimate on this selection."
            icon={<IconUsers className="h-[18px] w-[18px]" />}
          />
        ) : (
          <>
            {isLowConfidence && (
              <Callout tone="bad" icon={<IconAlert className="h-4 w-4" />}>
                Confidence is below 50% for this selection — treat the category breakdown below as low-reliability.
              </Callout>
            )}

            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              <StatCard
                label="Sample size"
                value={audience.sample_size.toLocaleString()}
                icon={<IconUsers className="h-4 w-4" />}
                tone="brand"
                footer={<span>Authors with usable signal</span>}
              />
              <StatCard
                label="Confidence"
                value={`${Math.round(audience.confidence * 100)}%`}
                icon={<IconShield className="h-4 w-4" />}
                tone={audience.confidence >= 0.5 ? "ok" : "bad"}
              />
              <StatCard
                label="Unknown share"
                value={`${Math.round(audience.unknown_share * 100)}%`}
                icon={<IconAlert className="h-4 w-4" />}
                tone={audience.unknown_share > 0.5 ? "warn" : "neutral"}
                footer={<span>Insufficient evidence to classify</span>}
              />
              <StatCard
                label="Categories"
                value={categoryEntries.length}
                icon={<IconTarget className="h-4 w-4" />}
                tone="neutral"
                footer={
                  topCategory ? (
                    <span>
                      Largest <span className="font-medium text-ink-2 capitalize">{topCategory[0]}</span>
                    </span>
                  ) : undefined
                }
              />
            </div>

            <Card
              title="Category distribution"
              subtitle={`Estimated from ${audience.sample_size.toLocaleString()} authors`}
            >
              <div className="flex flex-col items-center gap-7 lg:flex-row lg:items-start lg:gap-10">
                <Donut
                  slices={slices}
                  centerValue={topCategory ? `${Math.round(topCategory[1] * 100)}%` : "—"}
                  centerLabel={topCategory ? topCategory[0] : undefined}
                />

                <div className="w-full flex-1 space-y-3.5">
                  {categoryEntries.map(([category, share], i) => (
                    <Meter
                      key={category}
                      label={category}
                      value={`${Math.round(share * 100)}%`}
                      share={share}
                      tone={
                        (["brand", "accent", "info", "ok", "warn"] as const)[i % 5]
                      }
                    />
                  ))}
                  <div className="border-t border-line pt-3.5">
                    <Meter
                      label="unknown / insufficient evidence"
                      value={`${Math.round(audience.unknown_share * 100)}%`}
                      share={audience.unknown_share}
                      tone="neutral"
                    />
                  </div>
                </div>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
