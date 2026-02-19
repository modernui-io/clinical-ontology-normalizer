"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useSyntheaMetrics, useSyntheaPipelineResults } from "@/hooks/api/useSynthea";

function StatCard({ title, value, subtitle }: { title: string; value: string | number; subtitle?: string }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="text-sm text-muted-foreground">{title}</div>
        <div className="text-2xl font-bold mt-1">{value}</div>
        {subtitle && <div className="text-xs text-muted-foreground mt-1">{subtitle}</div>}
      </CardContent>
    </Card>
  );
}

function DocumentDrillDown({ documentId }: { documentId: string }) {
  const { data, isLoading } = useSyntheaPipelineResults(documentId);

  if (isLoading) return <div className="p-4 text-sm text-muted-foreground">Loading pipeline results...</div>;
  if (!data) return <div className="p-4 text-sm text-muted-foreground">No results available</div>;

  const coverageColor = data.concept_coverage_percent >= 80 ? "text-green-500" : data.concept_coverage_percent >= 50 ? "text-yellow-500" : "text-red-500";

  return (
    <div className="p-4 bg-muted/30 border-t space-y-4">
      <div className="grid grid-cols-5 gap-4 text-center text-sm">
        <div><span className="font-bold">{data.mention_count}</span> mentions</div>
        <div><span className="font-bold text-green-500">{data.mapped_mention_count}</span> mapped</div>
        <div><span className="font-bold text-red-500">{data.unmapped_mention_count}</span> unmapped</div>
        <div><span className="font-bold">{data.fact_count}</span> facts</div>
        <div><span className={`font-bold ${coverageColor}`}>{data.concept_coverage_percent}%</span> coverage</div>
      </div>

      {data.text_preview && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">Note Preview</div>
          <div className="text-xs bg-background rounded p-2 max-h-32 overflow-y-auto whitespace-pre-wrap font-mono">{data.text_preview}</div>
        </div>
      )}

      {data.mentions.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">Mentions ({data.mentions.length})</div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b"><th className="text-left p-1">Text</th><th className="p-1">Assertion</th><th className="p-1">Concept</th><th className="p-1">Domain</th><th className="p-1">Score</th></tr></thead>
              <tbody>
                {data.mentions.slice(0, 15).map((m) => (
                  <tr key={m.id} className="border-b border-muted">
                    <td className="p-1 font-medium max-w-[200px] truncate">{m.text}</td>
                    <td className="p-1 text-center"><Badge variant="outline" className="text-[10px]">{m.assertion}</Badge></td>
                    <td className="p-1">{m.concept_name ?? <span className="text-muted-foreground">unmapped</span>}</td>
                    <td className="p-1">{m.domain_id ?? "-"}</td>
                    <td className="p-1 text-center">{m.mapping_score?.toFixed(2) ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SyntheaValidationPage() {
  const { data: metrics, isLoading } = useSyntheaMetrics();
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    if (!metrics) return;
    setExporting(true);
    try {
      const blob = new Blob([JSON.stringify(metrics, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `synthea-validation-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto p-6 max-w-6xl">
        <div className="text-center text-muted-foreground py-12">Loading Synthea metrics...</div>
      </div>
    );
  }

  if (!metrics || metrics.total_documents === 0) {
    return (
      <div className="container mx-auto p-6 max-w-6xl space-y-6">
        <h1 className="text-3xl font-bold">Synthea Validation</h1>
        <Card>
          <CardContent className="pt-6 text-center py-12">
            <p className="text-muted-foreground">No Synthea documents imported yet.</p>
            <Button asChild className="mt-4">
              <Link href="/datasets/synthea">Import Synthea Data</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Synthea Validation</h1>
          <p className="text-muted-foreground mt-1">Pipeline metrics for Synthea synthetic patient encounters</p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href="/datasets">All Datasets</Link>
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
            {exporting ? "Exporting..." : "Download Report"}
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard title="Documents" value={metrics.total_documents.toLocaleString()} />
        <StatCard title="Mentions" value={metrics.total_mentions.toLocaleString()} />
        <StatCard title="Concept Coverage" value={`${metrics.concept_coverage_percent}%`} />
        <StatCard title="Avg Confidence" value={metrics.avg_confidence.toFixed(3)} />
      </div>

      {/* Processing Status */}
      <Card>
        <CardHeader><CardTitle>Processing Status</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-4">
            {Object.entries(metrics.status_breakdown).map(([status, count]) => (
              <Badge key={status} variant={status === "completed" ? "default" : status === "failed" ? "destructive" : "secondary"} className="text-sm px-3 py-1">
                {status}: {count}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Encounter Class Distribution */}
      {metrics.encounter_class_distribution.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Encounter Class Distribution</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {metrics.encounter_class_distribution.map((e) => {
                const pct = metrics.total_documents > 0 ? (e.count / metrics.total_documents * 100) : 0;
                return (
                  <div key={e.encounter_class} className="flex items-center gap-3">
                    <div className="w-32 text-sm capitalize">{e.encounter_class}</div>
                    <div className="flex-1 bg-muted rounded-full h-4 overflow-hidden">
                      <div className="bg-primary h-full rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="w-20 text-sm text-right">{e.count} ({pct.toFixed(0)}%)</div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Domain Distribution */}
      {metrics.domain_distribution.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Domain Distribution</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {metrics.domain_distribution.map((d) => {
                const maxCount = Math.max(...metrics.domain_distribution.map((x) => x.count));
                const pct = maxCount > 0 ? (d.count / maxCount * 100) : 0;
                return (
                  <div key={d.domain} className="flex items-center gap-3">
                    <div className="w-32 text-sm">{d.domain}</div>
                    <div className="flex-1 bg-muted rounded-full h-4 overflow-hidden">
                      <div className="bg-blue-500 h-full rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="w-16 text-sm text-right">{d.count}</div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Unmapped Terms */}
      {metrics.top_unmapped_terms.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Top Unmapped Terms</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead><tr className="border-b"><th className="text-left p-2">Term</th><th className="text-right p-2">Count</th></tr></thead>
              <tbody>
                {metrics.top_unmapped_terms.map((t) => (
                  <tr key={t.term} className="border-b border-muted">
                    <td className="p-2">{t.term}</td>
                    <td className="p-2 text-right">{t.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Performance */}
      <Card>
        <CardHeader><CardTitle>Processing Performance</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-xl font-bold">{metrics.avg_processing_time_ms.toFixed(0)} ms</div>
              <div className="text-sm text-muted-foreground">Average</div>
            </div>
            <div>
              <div className="text-xl font-bold">{metrics.p50_processing_time_ms.toFixed(0)} ms</div>
              <div className="text-sm text-muted-foreground">P50</div>
            </div>
            <div>
              <div className="text-xl font-bold">{metrics.p95_processing_time_ms.toFixed(0)} ms</div>
              <div className="text-sm text-muted-foreground">P95</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Documents */}
      {metrics.recent_documents.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Recent Documents</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Patient ID</th>
                  <th className="p-2">Encounter Class</th>
                  <th className="p-2">Description</th>
                  <th className="p-2">Status</th>
                  <th className="p-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {metrics.recent_documents.map((doc: Record<string, unknown>) => {
                  const docId = doc.id as string;
                  const isExpanded = expandedDocId === docId;
                  return (
                    <tr key={docId} className="border-b border-muted">
                      <td colSpan={5} className="p-0">
                        <div
                          className={`grid grid-cols-5 p-2 cursor-pointer hover:bg-muted/50 transition-colors ${isExpanded ? "bg-blue-50 dark:bg-blue-950/20" : ""}`}
                          onClick={() => setExpandedDocId(isExpanded ? null : docId)}
                        >
                          <div className="truncate">{doc.patient_id as string}</div>
                          <div className="text-center capitalize">{(doc.encounter_class as string) || "-"}</div>
                          <div className="text-center truncate">{(doc.encounter_description as string) || "-"}</div>
                          <div className="text-center">
                            <Badge variant={(doc.status as string) === "completed" ? "default" : "secondary"} className="text-xs">
                              {doc.status as string}
                            </Badge>
                          </div>
                          <div className="text-center text-xs">
                            {doc.created_at ? new Date(doc.created_at as string).toLocaleDateString() : "-"}
                          </div>
                        </div>
                        {isExpanded && <DocumentDrillDown documentId={docId} />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
