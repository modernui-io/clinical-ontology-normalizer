"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import {
  AlertTriangle,
  Loader2,
  ShieldAlert,
  Users,
  FileText,
  Activity,
} from "lucide-react";

interface ImpactResult {
  concept_id: number;
  concept_name: string;
  vocabulary_id: string;
  current_status: string;
  affected_kg_nodes: Array<{
    node_id: string;
    patient_id: string;
    node_type: string;
    label: string;
  }>;
  affected_patients: number;
  affected_rules: Array<{
    alert_rule_id: string;
    section_id: string;
    section_title: string;
  }>;
  risk_level: string;
  suggested_replacement: {
    concept_id: number;
    concept_name: string;
    vocabulary_id: string;
  } | null;
  total_affected_items: number;
}

interface ImpactAnalysisProps {
  conceptId: number;
  conceptName: string;
}

const RISK_COLORS: Record<string, string> = {
  none: "bg-gray-100 text-gray-800 border-gray-300",
  low: "bg-green-100 text-green-800 border-green-300",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
  high: "bg-red-100 text-red-800 border-red-300",
};

const CHART_COLORS: Record<string, string> = {
  none: "#9ca3af",
  low: "#22c55e",
  medium: "#eab308",
  high: "#ef4444",
};

function RiskBadge({ risk }: { risk: string }) {
  return (
    <Badge variant="outline" className={`${RISK_COLORS[risk] || ""} text-xs`}>
      {risk === "high" && <ShieldAlert className="h-3 w-3 mr-1" />}
      {risk.charAt(0).toUpperCase() + risk.slice(1)} Risk
    </Badge>
  );
}

export function ImpactAnalysis({ conceptId, conceptName }: ImpactAnalysisProps) {
  const [impact, setImpact] = useState<ImpactResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retiring, setRetiring] = useState(false);

  const analyzeImpact = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/vocabularies/concepts/${conceptId}/impact`);
      if (res.ok) {
        const data = await res.json();
        setImpact(data);
      } else {
        setError("Failed to analyze impact");
      }
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  };

  const handleRetire = async () => {
    if (!impact) return;
    setRetiring(true);
    try {
      const res = await fetch(`/api/vocabularies/concepts/${conceptId}/retire`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          replacement_concept_id: impact.suggested_replacement?.concept_id ?? null,
        }),
      });
      if (res.ok) {
        // Re-analyze to see updated state
        await analyzeImpact();
      }
    } catch {
      setError("Failed to retire concept");
    } finally {
      setRetiring(false);
    }
  };

  const chartData = impact
    ? [
        { name: "KG Nodes", value: impact.affected_kg_nodes.length, fill: "#3b82f6" },
        { name: "Patients", value: impact.affected_patients, fill: "#8b5cf6" },
        { name: "Rules", value: impact.affected_rules.length, fill: "#f97316" },
      ]
    : [];

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1" onClick={analyzeImpact}>
          <AlertTriangle className="h-3.5 w-3.5" />
          Analyze Impact
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Impact Analysis: {conceptName}
          </DialogTitle>
        </DialogHeader>
        <ScrollArea className="h-[60vh]">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
            </div>
          ) : error ? (
            <div className="text-center py-8 text-red-500">{error}</div>
          ) : impact ? (
            <div className="space-y-4 pr-4">
              {/* Risk Level */}
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">{impact.concept_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {impact.vocabulary_id} | Concept {impact.concept_id}
                  </div>
                </div>
                <RiskBadge risk={impact.risk_level} />
              </div>

              <Separator />

              {/* Impact Summary Chart */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Affected Items</CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart data={chartData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 12 }} />
                      <RechartsTooltip />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                        {chartData.map((entry, idx) => (
                          <Cell key={idx} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Affected Patients */}
              <Card>
                <CardHeader className="py-2 px-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Users className="h-4 w-4 text-purple-500" />
                    Affected Patients ({impact.affected_patients})
                  </CardTitle>
                </CardHeader>
                {impact.affected_kg_nodes.length > 0 && (
                  <CardContent className="pt-0 pb-3 px-3">
                    <div className="space-y-1 text-xs">
                      {impact.affected_kg_nodes.slice(0, 10).map((node, idx) => (
                        <div
                          key={idx}
                          className="flex justify-between rounded border p-1.5"
                        >
                          <span className="font-medium">{node.label}</span>
                          <Badge variant="outline" className="text-xs">
                            {node.node_type}
                          </Badge>
                        </div>
                      ))}
                      {impact.affected_kg_nodes.length > 10 && (
                        <div className="text-center text-muted-foreground pt-1">
                          + {impact.affected_kg_nodes.length - 10} more nodes
                        </div>
                      )}
                    </div>
                  </CardContent>
                )}
              </Card>

              {/* Affected Rules */}
              {impact.affected_rules.length > 0 && (
                <Card>
                  <CardHeader className="py-2 px-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Activity className="h-4 w-4 text-orange-500" />
                      Affected Alert Rules ({impact.affected_rules.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 pb-3 px-3">
                    <div className="space-y-1 text-xs">
                      {impact.affected_rules.map((rule, idx) => (
                        <div
                          key={idx}
                          className="flex justify-between rounded border p-1.5"
                        >
                          <span>{rule.section_title}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Suggested Replacement */}
              {impact.suggested_replacement && (
                <Card>
                  <CardHeader className="py-2 px-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FileText className="h-4 w-4 text-blue-500" />
                      Suggested Replacement
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 pb-3 px-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-indigo-600">
                        {impact.suggested_replacement.concept_id}
                      </span>
                      <span>{impact.suggested_replacement.concept_name}</span>
                      <Badge variant="secondary" className="text-xs">
                        {impact.suggested_replacement.vocabulary_id}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : null}
        </ScrollArea>
        {impact && impact.current_status === "active" && (
          <DialogFooter>
            <Button
              variant="destructive"
              onClick={handleRetire}
              disabled={retiring}
              className="gap-1"
            >
              {retiring ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ShieldAlert className="h-4 w-4" />
              )}
              Retire Concept
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
