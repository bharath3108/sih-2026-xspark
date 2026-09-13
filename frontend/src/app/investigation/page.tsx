"use client";

import { useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import type { Investigation, Report } from "@/lib/types";
import { Badge, Card, ConfidenceBadge } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Tabs } from "@/components/ui/Tabs";
import { IconDocument, IconSearchDoc, IconShield, IconSparkles } from "@/components/ui/Icons";

function StepBadge({ n, state }: { n: number; state: "done" | "active" | "todo" }) {
  const styles = {
    done: "border-ok/30 bg-ok-soft text-ok",
    active: "border-brand/40 bg-brand-soft text-brand",
    todo: "border-line bg-surface-2 text-ink-4",
  }[state];
  return (
    <span
      aria-hidden="true"
      className={`tnum flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold ${styles}`}
    >
      {state === "done" ? "✓" : n}
    </span>
  );
}

function Step({
  n,
  state,
  title,
  subtitle,
  actions,
  children,
}: {
  n: number;
  state: "done" | "active" | "todo";
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <StepBadge n={n} state={state} />
          <div className="min-w-0">
            <h3 className="text-[15px] leading-6 font-semibold text-ink">{title}</h3>
            {subtitle && <p className="mt-0.5 text-[13px] leading-5 text-ink-3">{subtitle}</p>}
          </div>
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      {children}
    </Card>
  );
}

/** Raw contract payload, kept verbatim so the audit trail stays inspectable. */
function JsonPanel({ value }: { value: Record<string, unknown> }) {
  return (
    <pre className="max-h-80 overflow-auto rounded-xl border border-line bg-base/70 p-3.5 font-mono text-[12px] leading-[1.65] text-ink-2">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export default function InvestigationPage() {
  const [selectedTopic, setSelectedTopic] = useState<string>("");
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState<"investigate" | "report" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const topicsQuery = useAsync(() => api.listTopics(), []);

  if (topicsQuery.loading) return <LoadingState label="Loading narratives…" />;
  if (topicsQuery.error) return <ErrorState message={topicsQuery.error} onRetry={topicsQuery.reload} />;

  const topics = topicsQuery.data?.topics ?? [];

  async function runInvestigation() {
    if (!selectedTopic) return;
    setBusy("investigate");
    setActionError(null);
    setReport(null);
    try {
      const result = await api.createInvestigation(selectedTopic);
      setInvestigation(result);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to build the investigation.");
    } finally {
      setBusy(null);
    }
  }

  async function runReport() {
    if (!investigation) return;
    setBusy("report");
    setActionError(null);
    try {
      const result = await api.createReport(investigation);
      setReport(result);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to generate the report.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="animate-fade-rise">
      <PageHeader
        title="Investigation"
        description="Assemble a cross-dimensional explanation for one narrative, then generate a reportable summary with a full audit trail."
      />

      <div className="space-y-4">
        <Step
          n={1}
          state={investigation ? "done" : "active"}
          title="Select an anomaly or narrative"
          subtitle="Pick the narrative you want explained across narrative, NLP, audience and network dimensions."
        >
          {topics.length === 0 ? (
            <EmptyState message="No narratives available to investigate yet." />
          ) : (
            <div className="flex flex-wrap items-center gap-2.5">
              <Select
                caption="Narrative"
                srLabel="Select a narrative to investigate"
                value={selectedTopic}
                onChange={(e) => setSelectedTopic(e.target.value)}
                className="min-w-0 flex-1 sm:flex-none"
              >
                <option value="">Choose a narrative…</option>
                {topics.map((t) => (
                  <option key={t.topic_id} value={t.topic_id}>
                    {t.name} (trend {t.metrics.trend_score.toFixed(2)})
                  </option>
                ))}
              </Select>
              <Button
                onClick={runInvestigation}
                disabled={!selectedTopic || busy !== null}
                loading={busy === "investigate"}
                variant="primary"
                icon={<IconSparkles className="h-4 w-4" />}
              >
                {busy === "investigate" ? "Building…" : "Build cross-dimensional explanation"}
              </Button>
            </div>
          )}
        </Step>

        {actionError && <ErrorState message={actionError} />}

        {investigation && (
          <Step
            n={2}
            state={report ? "done" : "active"}
            title="Cross-dimensional finding"
            subtitle={`Investigation ${investigation.investigation_id}`}
            actions={
              <Button
                onClick={runReport}
                disabled={busy !== null}
                loading={busy === "report"}
                variant="primary"
                icon={<IconDocument className="h-4 w-4" />}
              >
                {busy === "report" ? "Generating…" : "Generate report"}
              </Button>
            }
          >
            <Tabs
              ariaLabel="Finding dimensions"
              items={[
                { id: "narrative", label: "Narrative", content: <JsonPanel value={investigation.finding.narrative} /> },
                { id: "nlp", label: "NLP", content: <JsonPanel value={investigation.finding.nlp} /> },
                { id: "audience", label: "Audience", content: <JsonPanel value={investigation.finding.audience} /> },
                { id: "network", label: "Network", content: <JsonPanel value={investigation.finding.network} /> },
              ]}
            />

            <div className="mt-5">
              <div className="mb-2.5 flex items-center gap-2">
                <h4 className="text-[13px] font-semibold text-ink">Claims</h4>
                <Badge tone="neutral">
                  <span className="tnum">{investigation.claims.length}</span>
                </Badge>
              </div>
              {investigation.claims.length === 0 ? (
                <EmptyState message="No claims met the confidence/evidence bar for this narrative." compact />
              ) : (
                <ul className="space-y-2">
                  {investigation.claims.map((c, i) => (
                    <li
                      key={i}
                      className="rounded-xl border border-line bg-surface-2/40 p-3.5 transition-colors duration-150 hover:border-line-strong"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-[13px] leading-[1.6] text-ink">{c.claim}</p>
                        <ConfidenceBadge confidence={c.confidence} />
                      </div>
                      <p className="mt-2 border-t border-line pt-2 font-mono text-[11px] break-all text-ink-4">
                        Evidence: {c.evidence_event_ids.join(", ")}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {investigation.models.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-line pt-3.5">
                <span className="text-[11px] text-ink-4">Models</span>
                {investigation.models.map((m) => (
                  <Badge key={`${m.name}@${m.version}`} tone="neutral" className="font-mono">
                    {m.name}@{m.version}
                  </Badge>
                ))}
              </div>
            )}
          </Step>
        )}

        {report && (
          <Step
            n={3}
            state="done"
            title="Report"
            subtitle={`Report ${report.report_id}`}
            actions={
              <Badge tone={report.generated_by.fallback_reason ? "warn" : "ok"} dot>
                {report.generated_by.mode}
              </Badge>
            }
          >
            <div className="rounded-xl border border-line bg-surface-2/40 p-4">
              <p className="text-[14px] leading-[1.75] whitespace-pre-line text-ink">{report.narrative_text}</p>
            </div>

            <div className="mt-4 rounded-xl border border-line bg-base/60 p-4">
              <div className="mb-2.5 flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-ok-soft text-ok">
                  <IconShield className="h-3.5 w-3.5" />
                </span>
                <h4 className="text-[13px] font-semibold text-ink">Audit record</h4>
              </div>
              {/* Each row is a single text node so the whole "label: value"
                  string stays greppable and copyable as one line. */}
              <div className="space-y-2 text-[12px] leading-5 text-ink-2">
                <p>
                  <span className="text-ink-4">Generated by:</span> {report.generated_by.mode} (
                  {report.generated_by.model})
                </p>
                {report.generated_by.fallback_reason && (
                  <p className="text-warn">
                    <span className="text-ink-4">Fallback reason:</span> {report.generated_by.fallback_reason}
                  </p>
                )}
                <p>
                  <span className="text-ink-4">Models used:</span>{" "}
                  <span className="font-mono">
                    {report.audit.models.map((m) => `${m.name}@${m.version}`).join(", ")}
                  </span>
                </p>
                <p>
                  <span className="text-ink-4">Evidence event IDs:</span>{" "}
                  <span className="font-mono break-all">
                    {report.audit.inputs.evidence_event_ids.join(", ") || "none"}
                  </span>
                </p>
                <p>
                  <span className="text-ink-4">Generated at:</span>{" "}
                  <span className="tnum">{report.audit.generated_at_utc}</span>
                </p>
              </div>
            </div>
          </Step>
        )}

        {!investigation && topics.length > 0 && (
          <Card>
            <EmptyState
              message="Select a narrative above and build an explanation to see the cross-dimensional finding and report here."
              icon={<IconSearchDoc className="h-[18px] w-[18px]" />}
            />
          </Card>
        )}
      </div>
    </div>
  );
}
