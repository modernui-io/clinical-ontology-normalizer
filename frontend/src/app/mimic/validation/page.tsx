"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useMimicMetrics, useMimicPipelineResults } from "@/hooks/api/useMimic";
import { exportMimicMetrics } from "@/lib/api";

function StatCard({
  label,
  value,
  subtext,
  color,
}: {
  label: string;
  value: string | number;
  subtext?: string;
  color?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm font-medium text-zinc-500">{label}</p>
        <p className={`text-3xl font-bold ${color || "text-zinc-900 dark:text-zinc-100"}`}>
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>
        {subtext && <p className="mt-1 text-xs text-zinc-400">{subtext}</p>}
      </CardContent>
    </Card>
  );
}

function DocumentDrillDown({ documentId, onClose }: { documentId: string; onClose: () => void }) {
  const { data: results, isLoading, error } = useMimicPipelineResults(documentId);

  if (isLoading) {
    return (
      <tr>
        <td colSpan={5} className="bg-zinc-50 px-4 py-6 dark:bg-zinc-800/50">
          <div className="text-center text-sm text-zinc-500">Loading pipeline results...</div>
        </td>
      </tr>
    );
  }

  if (error || !results) {
    return (
      <tr>
        <td colSpan={5} className="bg-zinc-50 px-4 py-6 dark:bg-zinc-800/50">
          <div className="text-center text-sm text-red-500">
            Failed to load pipeline results.{" "}
            <button onClick={onClose} className="underline">Close</button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr>
      <td colSpan={5} className="bg-zinc-50 p-0 dark:bg-zinc-800/50">
        <div className="border-t border-b border-blue-200 px-4 py-4 dark:border-blue-800">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Pipeline Results — {results.mimic_note_id || results.document_id.slice(0, 8)}
            </h4>
            <button
              onClick={onClose}
              className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
            >
              Close
            </button>
          </div>

          {/* Summary stats row */}
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <div className="rounded bg-white p-2 text-center dark:bg-zinc-900">
              <p className="text-lg font-bold">{results.mention_count}</p>
              <p className="text-xs text-zinc-500">Mentions</p>
            </div>
            <div className="rounded bg-white p-2 text-center dark:bg-zinc-900">
              <p className="text-lg font-bold">{results.mapped_mention_count}</p>
              <p className="text-xs text-zinc-500">Mapped</p>
            </div>
            <div className="rounded bg-white p-2 text-center dark:bg-zinc-900">
              <p className="text-lg font-bold">{results.unmapped_mention_count}</p>
              <p className="text-xs text-zinc-500">Unmapped</p>
            </div>
            <div className="rounded bg-white p-2 text-center dark:bg-zinc-900">
              <p className="text-lg font-bold">{results.fact_count}</p>
              <p className="text-xs text-zinc-500">Facts</p>
            </div>
            <div className="rounded bg-white p-2 text-center dark:bg-zinc-900">
              <p className={`text-lg font-bold ${results.concept_coverage_percent >= 80 ? "text-green-600" : results.concept_coverage_percent >= 50 ? "text-yellow-600" : "text-red-600"}`}>
                {results.concept_coverage_percent.toFixed(1)}%
              </p>
              <p className="text-xs text-zinc-500">Coverage</p>
            </div>
          </div>

          {/* Text preview */}
          <div className="mb-4 rounded border bg-white p-3 dark:bg-zinc-900">
            <p className="mb-1 text-xs font-medium text-zinc-500">
              Text Preview ({results.text_length.toLocaleString()} chars)
            </p>
            <p className="text-xs text-zinc-700 dark:text-zinc-300">
              {results.text_preview}
            </p>
          </div>

          {/* Mentions table */}
          {results.mentions.length > 0 && (
            <div className="mb-4">
              <p className="mb-2 text-xs font-medium text-zinc-500">
                Mentions ({results.mentions.length})
              </p>
              <div className="max-h-56 overflow-auto rounded border bg-white dark:bg-zinc-900">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-800">
                    <tr>
                      <th className="px-2 py-1.5 text-left font-medium">Text</th>
                      <th className="px-2 py-1.5 text-left font-medium">Assertion</th>
                      <th className="px-2 py-1.5 text-left font-medium">Concept</th>
                      <th className="px-2 py-1.5 text-left font-medium">Domain</th>
                      <th className="px-2 py-1.5 text-right font-medium">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.mentions.map((m) => (
                      <tr key={m.id} className="border-t">
                        <td className="max-w-[200px] truncate px-2 py-1.5 font-mono">
                          {m.text}
                        </td>
                        <td className="px-2 py-1.5">
                          <Badge
                            variant={m.assertion === "present" ? "default" : "secondary"}
                            className="text-[10px]"
                          >
                            {m.assertion}
                          </Badge>
                        </td>
                        <td className="max-w-[180px] truncate px-2 py-1.5">
                          {m.concept_name ? (
                            <span title={`OMOP ${m.omop_concept_id} (${m.vocabulary_id})`}>
                              {m.concept_name}
                            </span>
                          ) : (
                            <span className="text-zinc-400">unmapped</span>
                          )}
                        </td>
                        <td className="px-2 py-1.5">{m.domain_id || "-"}</td>
                        <td className="px-2 py-1.5 text-right">
                          {m.mapping_score != null ? m.mapping_score.toFixed(2) : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Facts table */}
          {results.facts.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-zinc-500">
                Clinical Facts ({results.facts.length})
              </p>
              <div className="max-h-44 overflow-auto rounded border bg-white dark:bg-zinc-900">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-800">
                    <tr>
                      <th className="px-2 py-1.5 text-left font-medium">Concept</th>
                      <th className="px-2 py-1.5 text-left font-medium">Domain</th>
                      <th className="px-2 py-1.5 text-left font-medium">Assertion</th>
                      <th className="px-2 py-1.5 text-left font-medium">Temporality</th>
                      <th className="px-2 py-1.5 text-right font-medium">Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.facts.map((f) => (
                      <tr key={f.id} className="border-t">
                        <td className="max-w-[200px] truncate px-2 py-1.5">
                          <span title={`OMOP ${f.omop_concept_id}`}>{f.concept_name}</span>
                        </td>
                        <td className="px-2 py-1.5 capitalize">{f.domain}</td>
                        <td className="px-2 py-1.5">
                          <Badge
                            variant={f.assertion === "present" ? "default" : "secondary"}
                            className="text-[10px]"
                          >
                            {f.assertion}
                          </Badge>
                        </td>
                        <td className="px-2 py-1.5">{f.temporality}</td>
                        <td className="px-2 py-1.5 text-right">{f.confidence.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function MimicValidationDashboard() {
  const { data: metrics, isLoading, error } = useMimicMetrics();
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const data = await exportMimicMetrics();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mimic-validation-report-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Error logged by query client error handler
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/mimic" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                &larr; MIMIC Import
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                MIMIC Validation Dashboard
              </h1>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleExport}
                disabled={exporting || !metrics}
              >
                {exporting ? "Exporting..." : "Download Report"}
              </Button>
              <Link href="/mimic">
                <Button variant="outline" size="sm">Import More</Button>
              </Link>
            </div>
          </div>
          <p className="mt-1 text-sm text-zinc-500">
            Pipeline validation metrics for MIMIC-IV-Note imported documents
          </p>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-zinc-500">Loading metrics...</div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 dark:bg-red-900/20 dark:text-red-400">
            Failed to load metrics. Is the backend running?
          </div>
        )}

        {metrics && (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard label="Total Documents" value={metrics.total_documents} />
              <StatCard label="Total Mentions" value={metrics.total_mentions} />
              <StatCard
                label="Concept Coverage"
                value={`${metrics.concept_coverage_percent}%`}
                color={
                  metrics.concept_coverage_percent >= 80
                    ? "text-green-600"
                    : metrics.concept_coverage_percent >= 50
                    ? "text-yellow-600"
                    : "text-red-600"
                }
              />
              <StatCard
                label="Avg Confidence"
                value={metrics.avg_confidence.toFixed(3)}
              />
            </div>

            {/* Processing Status Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle>Processing Status</CardTitle>
                <CardDescription>Breakdown of document processing states</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(metrics.status_breakdown).map(([status, count]) => (
                    <div key={status} className="rounded-lg border px-4 py-3 text-center">
                      <p className="text-xl font-bold">{count.toLocaleString()}</p>
                      <Badge
                        variant={
                          status === "completed" ? "default" :
                          status === "failed" ? "destructive" :
                          "secondary"
                        }
                      >
                        {status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Domain Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Domain Distribution</CardTitle>
                <CardDescription>Clinical facts by OMOP domain ({metrics.total_facts.toLocaleString()} total)</CardDescription>
              </CardHeader>
              <CardContent>
                {metrics.domain_distribution.length === 0 ? (
                  <p className="text-sm text-zinc-500">No facts extracted yet</p>
                ) : (
                  <div className="space-y-2">
                    {metrics.domain_distribution.map((d) => {
                      const pct = metrics.total_facts > 0
                        ? (d.count / metrics.total_facts) * 100
                        : 0;
                      return (
                        <div key={d.domain} className="flex items-center gap-3">
                          <span className="w-28 text-sm font-medium capitalize">{d.domain}</span>
                          <div className="flex-1">
                            <div className="h-4 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                              <div
                                className="h-full rounded-full bg-blue-500"
                                style={{ width: `${Math.max(pct, 1)}%` }}
                              />
                            </div>
                          </div>
                          <span className="w-20 text-right text-sm text-zinc-500">
                            {d.count.toLocaleString()} ({pct.toFixed(1)}%)
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Top Unmapped Terms */}
            <Card>
              <CardHeader>
                <CardTitle>Top Unmapped Terms</CardTitle>
                <CardDescription>Mentions without OMOP concept mappings (pipeline gaps)</CardDescription>
              </CardHeader>
              <CardContent>
                {metrics.top_unmapped_terms.length === 0 ? (
                  <p className="text-sm text-zinc-500">All terms mapped successfully</p>
                ) : (
                  <div className="max-h-64 overflow-auto rounded border">
                    <table className="w-full text-sm">
                      <thead className="bg-zinc-100 dark:bg-zinc-800">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">Term</th>
                          <th className="px-3 py-2 text-right font-medium">Count</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.top_unmapped_terms.map((term) => (
                          <tr key={term.term} className="border-t">
                            <td className="px-3 py-2 font-mono text-xs">{term.term}</td>
                            <td className="px-3 py-2 text-right">{term.count.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Processing Performance */}
            <Card>
              <CardHeader>
                <CardTitle>Processing Performance</CardTitle>
                <CardDescription>NLP pipeline processing times</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div className="rounded-lg bg-zinc-100 p-4 dark:bg-zinc-800">
                    <p className="text-2xl font-bold">{metrics.avg_processing_time_ms.toFixed(0)}</p>
                    <p className="text-xs text-zinc-500">Avg (ms)</p>
                  </div>
                  <div className="rounded-lg bg-zinc-100 p-4 dark:bg-zinc-800">
                    <p className="text-2xl font-bold">{metrics.p50_processing_time_ms.toFixed(0)}</p>
                    <p className="text-xs text-zinc-500">P50 (ms)</p>
                  </div>
                  <div className="rounded-lg bg-zinc-100 p-4 dark:bg-zinc-800">
                    <p className="text-2xl font-bold">{metrics.p95_processing_time_ms.toFixed(0)}</p>
                    <p className="text-xs text-zinc-500">P95 (ms)</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Recent Documents with Drill-Down */}
            <Card>
              <CardHeader>
                <CardTitle>Recent Documents</CardTitle>
                <CardDescription>
                  Click any row to see full pipeline output (mentions, concept mappings, facts)
                </CardDescription>
              </CardHeader>
              <CardContent>
                {metrics.recent_documents.length === 0 ? (
                  <p className="text-sm text-zinc-500">No documents imported yet</p>
                ) : (
                  <div className="overflow-auto rounded border">
                    <table className="w-full text-sm">
                      <thead className="bg-zinc-100 dark:bg-zinc-800">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">MIMIC Note ID</th>
                          <th className="px-3 py-2 text-left font-medium">Patient</th>
                          <th className="px-3 py-2 text-left font-medium">Note Type</th>
                          <th className="px-3 py-2 text-left font-medium">Status</th>
                          <th className="px-3 py-2 text-left font-medium">Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.recent_documents.map((doc) => {
                          const docId = doc.id as string;
                          const isExpanded = expandedDocId === docId;
                          return (
                            <>
                              <tr
                                key={docId}
                                onClick={() => setExpandedDocId(isExpanded ? null : docId)}
                                className={`cursor-pointer border-t transition-colors hover:bg-blue-50 dark:hover:bg-blue-900/10 ${isExpanded ? "bg-blue-50 dark:bg-blue-900/10" : ""}`}
                              >
                                <td className="px-3 py-2">
                                  <span className="font-mono text-xs text-blue-600">
                                    {(doc.mimic_note_id as string) || docId.slice(0, 8)}
                                  </span>
                                </td>
                                <td className="px-3 py-2 text-xs">{doc.patient_id as string}</td>
                                <td className="px-3 py-2 text-xs">{doc.note_type as string}</td>
                                <td className="px-3 py-2">
                                  <Badge
                                    variant={
                                      doc.status === "completed" ? "default" :
                                      doc.status === "failed" ? "destructive" :
                                      "secondary"
                                    }
                                    className="text-xs"
                                  >
                                    {doc.status as string}
                                  </Badge>
                                </td>
                                <td className="px-3 py-2 text-xs text-zinc-500">
                                  {doc.created_at ? new Date(doc.created_at as string).toLocaleString() : "-"}
                                </td>
                              </tr>
                              {isExpanded && (
                                <DocumentDrillDown
                                  key={`${docId}-drill`}
                                  documentId={docId}
                                  onClose={() => setExpandedDocId(null)}
                                />
                              )}
                            </>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
