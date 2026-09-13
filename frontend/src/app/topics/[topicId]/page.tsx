"use client";

import { use } from "react";
import Link from "next/link";
import type { Data } from "plotly.js";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Badge, Card, Meter, StatCard } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { PlotlyChart } from "@/components/charts/PlotlyChart";
import { PageHeader } from "@/components/ui/PageHeader";
import { colorForCommunity } from "@/components/charts/NetworkGraph";
import {
  IconChevronLeft,
  IconLayers,
  IconShare,
  IconSparkles,
  IconTarget,
  IconTrend,
  IconUsers,
} from "@/components/ui/Icons";
import type { NLPOutput } from "@/lib/types";

const SENTIMENT_TONE: Record<string, "ok" | "bad" | "neutral"> = {
  positive: "ok",
  negative: "bad",
  neutral: "neutral",
};

const STANCE_TONE: Record<string, "ok" | "bad" | "info" | "neutral"> = {
  support: "ok",
  oppose: "bad",
  neutral: "info",
  unknown: "neutral",
};

function tally(values: string[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

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

  const allCommunityIds = Array.from(new Set(network.topology.nodes.map((n) => n.community_id)));

  const nlpByEvent = new Map<string, NLPOutput>(topic.nlp_outputs.map((n) => [n.event_id, n]));
  const sentimentTally = tally(topic.nlp_outputs.map((n) => n.sentiment.label));
  const stanceTally = tally(topic.nlp_outputs.map((n) => n.stance.label));
  const nlpTotal = topic.nlp_outputs.length;

  const evolutionTrace: Data = {
    type: "scatter",
    mode: "lines",
    name: "volume",
    x: topic.timeline.map((p) => p.bucket_start),
    y: topic.timeline.map((p) => p.volume),
    line: { color: "#7c5cff", width: 2, shape: "spline", smoothing: 0.6 },
    fill: "tozeroy",
    fillcolor: "rgba(124, 92, 255, 0.13)",
    hovertemplate: "%{y:,} events<extra></extra>",
  };

  const windowLabel = `${new Date(topic.window.start).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })} – ${new Date(topic.window.end).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;

  return (
    <div className="animate-fade-rise">
      <PageHeader
        title={topic.name}
        description={`Window ${windowLabel} · ${topic.metrics.volume.toLocaleString()} posts from ${topic.metrics.unique_authors.toLocaleString()} authors`}
        eyebrow={
          <Link
            href="/topics"
            className="mb-1.5 inline-flex items-center gap-1 text-[12px] text-ink-3 transition-colors hover:text-brand"
          >
            <IconChevronLeft className="h-3.5 w-3.5" />
            Narratives
          </Link>
        }
        actions={
          <>
            <Badge tone="neutral" className="font-mono">
              {topic.topic_id}
            </Badge>
            <Link
              href="/investigation"
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-brand px-3.5 text-sm font-medium text-white shadow-[0_1px_0_#ffffff26_inset,0_6px_16px_-8px_#7c5cffcc] transition-colors hover:bg-brand-hi"
            >
              <IconSparkles className="h-4 w-4" />
              Investigate
            </Link>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label="Trend score"
          value={topic.metrics.trend_score.toFixed(2)}
          icon={<IconTrend className="h-4 w-4" />}
          tone={topic.metrics.trend_score >= 0.85 ? "bad" : "accent"}
        />
        <StatCard label="Novelty" value={topic.metrics.novelty.toFixed(2)} icon={<IconSparkles className="h-4 w-4" />} tone="brand" />
        <StatCard
          label="Cross-community spread"
          value={topic.metrics.cross_community_spread.toFixed(2)}
          icon={<IconShare className="h-4 w-4" />}
          tone="neutral"
        />
        <StatCard
          label="Affected communities"
          value={affectedCommunityIds.size}
          icon={<IconTarget className="h-4 w-4" />}
          tone="neutral"
          footer={<span>of {network.communities.length} total</span>}
        />
      </div>

      <div className="mt-4">
        <Card title="Topic evolution" subtitle="Event volume per bucket across the detection window">
          {topic.timeline.length === 0 ? (
            <EmptyState message="No timeline points recorded for this narrative." />
          ) : (
            <PlotlyChart data={[evolutionTrace]} height={260} layout={{ yaxis: { rangemode: "tozero" } }} />
          )}
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card
          title="Sentiment, emotion & stance"
          subtitle={nlpTotal > 0 ? `Across ${nlpTotal} classified evidence events` : undefined}
          className="lg:col-span-2"
        >
          {nlpTotal === 0 ? (
            <EmptyState message="No NLP signal attached to this narrative's evidence yet." />
          ) : (
            <div className="grid grid-cols-1 gap-x-8 gap-y-5 sm:grid-cols-2">
              <div>
                <p className="mb-3 text-[11px] font-semibold tracking-[0.06em] text-ink-4 uppercase">Sentiment</p>
                <div className="space-y-3">
                  {sentimentTally.map(([label, count]) => (
                    <Meter
                      key={label}
                      label={label}
                      value={`${count} · ${Math.round((count / nlpTotal) * 100)}%`}
                      share={count / nlpTotal}
                      tone={SENTIMENT_TONE[label] ?? "neutral"}
                    />
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-3 text-[11px] font-semibold tracking-[0.06em] text-ink-4 uppercase">Stance</p>
                <div className="space-y-3">
                  {stanceTally.map(([label, count]) => (
                    <Meter
                      key={label}
                      label={label}
                      value={`${count} · ${Math.round((count / nlpTotal) * 100)}%`}
                      share={count / nlpTotal}
                      tone={STANCE_TONE[label] === "info" ? "info" : STANCE_TONE[label] ?? "neutral"}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>

        <Card title="Affected communities" subtitle="Communities touched by this narrative's evidence">
          {affectedCommunityIds.size === 0 ? (
            <EmptyState
              message="No community linkage found for this narrative's evidence yet."
              icon={<IconShare className="h-[18px] w-[18px]" />}
              compact
            />
          ) : (
            <ul className="space-y-1.5">
              {[...affectedCommunityIds].map((cid) => {
                const community = network.communities.find((c) => c.community_id === cid);
                return (
                  <li
                    key={cid}
                    className="flex items-center gap-2.5 rounded-lg border border-line bg-surface-2/50 px-3 py-2"
                  >
                    <span
                      aria-hidden="true"
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: colorForCommunity(cid, allCommunityIds) }}
                    />
                    <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-ink-2">{cid}</span>
                    <span className="tnum shrink-0 text-[12px] text-ink-4">{community?.size ?? "?"} members</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-4">
        <Card
          title="Evidence"
          subtitle="Source events backing this narrative, with their model classifications"
          actions={
            <Badge tone="neutral">
              <span className="tnum font-semibold">{topic.evidence_events.length}</span> events
            </Badge>
          }
        >
          {topic.evidence_events.length === 0 ? (
            <EmptyState message="No evidence events on record for this narrative." />
          ) : (
            <ul className="space-y-2.5">
              {topic.evidence_events.map((e) => {
                const nlp = nlpByEvent.get(e.event_id);
                return (
                  <li
                    key={e.event_id}
                    className="rounded-xl border border-line bg-surface-2/40 p-3.5 transition-colors duration-150 hover:border-line-strong hover:bg-surface-2/70"
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-1.5">
                      <Badge tone="brand" className="uppercase">
                        {e.source}
                      </Badge>
                      {nlp && (
                        <>
                          <Badge tone={SENTIMENT_TONE[nlp.sentiment.label] ?? "neutral"} dot>
                            <span className="capitalize">{nlp.sentiment.label}</span>
                            <span className="tnum opacity-70">{Math.round(nlp.sentiment.confidence * 100)}%</span>
                          </Badge>
                          {nlp.emotion && (
                            <Badge tone="neutral">
                              <span className="capitalize">{nlp.emotion.label}</span>
                            </Badge>
                          )}
                          <Badge tone={STANCE_TONE[nlp.stance.label] ?? "neutral"}>
                            stance: <span className="capitalize">{nlp.stance.label}</span>
                          </Badge>
                        </>
                      )}
                      <span className="ml-auto font-mono text-[11px] text-ink-4">{e.event_id}</span>
                    </div>

                    <p className="text-[13px] leading-[1.6] text-ink">{e.text}</p>

                    <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2 text-[11px] text-ink-4">
                      <span className="tnum">{new Date(e.timestamp_utc).toLocaleString()}</span>
                      <span aria-hidden="true">·</span>
                      <span className="tnum">{e.engagement.likes.toLocaleString()} likes</span>
                      <span aria-hidden="true">·</span>
                      <span className="tnum">{e.engagement.shares.toLocaleString()} shares</span>
                      <span aria-hidden="true">·</span>
                      <span className="tnum">{e.engagement.comments.toLocaleString()} comments</span>
                      {e.language && (
                        <>
                          <span aria-hidden="true">·</span>
                          <span className="uppercase">{e.language}</span>
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-4">
        <Card title="Audience estimate" subtitle="Aggregate, probabilistic — not an identity claim">
          {topic.audience.sample_size === 0 ? (
            <EmptyState message="Insufficient evidence for an audience estimate on this narrative." icon={<IconUsers className="h-[18px] w-[18px]" />} compact />
          ) : (
            <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
              <div className="space-y-3">
                {Object.entries(topic.audience.categories).map(([category, share]) => (
                  <Meter
                    key={category}
                    label={category}
                    value={`${Math.round(share * 100)}%`}
                    share={share}
                    tone="brand"
                  />
                ))}
                <Meter
                  label="unknown / insufficient evidence"
                  value={`${Math.round(topic.audience.unknown_share * 100)}%`}
                  share={topic.audience.unknown_share}
                  tone="neutral"
                />
              </div>
              <dl className="grid grid-cols-2 gap-3 self-start">
                <div className="rounded-lg border border-line bg-surface-2/50 px-3 py-2.5">
                  <dt className="text-[11px] text-ink-4">Sample size</dt>
                  <dd className="tnum mt-0.5 text-[16px] font-semibold text-ink">{topic.audience.sample_size}</dd>
                </div>
                <div className="rounded-lg border border-line bg-surface-2/50 px-3 py-2.5">
                  <dt className="text-[11px] text-ink-4">Confidence</dt>
                  <dd className="tnum mt-0.5 text-[16px] font-semibold text-ink">
                    {Math.round(topic.audience.confidence * 100)}%
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-4 flex justify-center pb-2">
        <Link
          href="/topics"
          className="inline-flex items-center gap-1.5 text-[13px] text-ink-3 transition-colors hover:text-brand"
        >
          <IconLayers className="h-4 w-4" />
          Back to all narratives
        </Link>
      </div>
    </div>
  );
}
