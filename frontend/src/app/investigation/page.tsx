"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import type { Investigation, Report } from "@/lib/types";
import { Card, ConfidenceBadge } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/States";

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
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Investigation</h1>

      <Card title="1. Select an anomaly / narrative">
        {topics.length === 0 ? (
          <EmptyState message="No narratives available to investigate yet." />
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <select
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
              value={selectedTopic}
              onChange={(e) => setSelectedTopic(e.target.value)}
            >
              <option value="">Choose a narrative…</option>
              {topics.map((t) => (
                <option key={t.topic_id} value={t.topic_id}>
                  {t.name} (trend {t.metrics.trend_score.toFixed(2)})
                </option>
              ))}
            </select>
            <button
              onClick={runInvestigation}
              disabled={!selectedTopic || busy !== null}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            >
              {busy === "investigate" ? "Building…" : "Build cross-dimensional explanation"}
            </button>
          </div>
        )}
      </Card>

      {actionError && <ErrorState message={actionError} />}

      {investigation && (
        <Card title="2. Cross-dimensional finding">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Narrative</p>
              <pre className="mt-1 overflow-x-auto rounded-md bg-slate-50 p-2 text-xs">
                {JSON.stringify(investigation.finding.narrative, null, 2)}
              </pre>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">NLP</p>
              <pre className="mt-1 overflow-x-auto rounded-md bg-slate-50 p-2 text-xs">
                {JSON.stringify(investigation.finding.nlp, null, 2)}
              </pre>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Audience</p>
              <pre className="mt-1 overflow-x-auto rounded-md bg-slate-50 p-2 text-xs">
                {JSON.stringify(investigation.finding.audience, null, 2)}
              </pre>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Network</p>
              <pre className="mt-1 overflow-x-auto rounded-md bg-slate-50 p-2 text-xs">
                {JSON.stringify(investigation.finding.network, null, 2)}
              </pre>
            </div>
          </div>

          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Claims</p>
            {investigation.claims.length === 0 ? (
              <EmptyState message="No claims met the confidence/evidence bar for this narrative." />
            ) : (
              <ul className="space-y-2">
                {investigation.claims.map((c, i) => (
                  <li key={i} className="rounded-md border border-slate-200 p-3 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <p>{c.claim}</p>
                      <ConfidenceBadge confidence={c.confidence} />
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      Evidence: {c.evidence_event_ids.join(", ")}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <button
            onClick={runReport}
            disabled={busy !== null}
            className="mt-4 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            {busy === "report" ? "Generating…" : "Generate report"}
          </button>
        </Card>
      )}

      {report && (
        <Card title="3. Report">
          <p className="whitespace-pre-line text-sm text-slate-800">{report.narrative_text}</p>

          <div className="mt-4 rounded-md bg-slate-50 p-3 text-xs text-slate-600">
            <p className="font-semibold text-slate-700">Audit record</p>
            <p>Generated by: {report.generated_by.mode} ({report.generated_by.model})</p>
            {report.generated_by.fallback_reason && (
              <p className="text-amber-700">Fallback reason: {report.generated_by.fallback_reason}</p>
            )}
            <p>Models used: {report.audit.models.map((m) => `${m.name}@${m.version}`).join(", ")}</p>
            <p>Evidence event IDs: {report.audit.inputs.evidence_event_ids.join(", ") || "none"}</p>
            <p>Generated at: {report.audit.generated_at_utc}</p>
          </div>
        </Card>
      )}
    </div>
  );
}
