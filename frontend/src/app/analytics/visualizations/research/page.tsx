"use client";

import { useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Microscope,
  BarChart2,
  Calendar,
  Info,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  Clock,
  AlertCircle,
  Circle,
} from "lucide-react";
import {
  ScatterChart,
  Scatter as RechartsScatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  BarChart,
  Bar,
  Rectangle,
  ComposedChart,
  Line,
  ErrorBar,
} from "recharts";

// Types
interface ForestPlotStudy {
  study_id: string;
  study_name: string;
  year: number;
  effect_size: number;
  ci_lower: number;
  ci_upper: number;
  weight: number;
  sample_size: number;
  events_treatment: number | null;
  events_control: number | null;
  n_treatment: number | null;
  n_control: number | null;
}

interface ForestPlotData {
  studies: ForestPlotStudy[];
  pooled_effect: number;
  pooled_ci_lower: number;
  pooled_ci_upper: number;
  heterogeneity_i2: number;
  heterogeneity_q: number;
  heterogeneity_p: number;
  effect_measure: string;
  null_value: number;
}

interface VolcanoPoint {
  id: string;
  name: string;
  log_fold_change: number;
  neg_log_p_value: number;
  p_value: number;
  significant: boolean;
  direction: string;
  category: string | null;
}

interface VolcanoData {
  points: VolcanoPoint[];
  fc_threshold: number;
  p_threshold: number;
  total_features: number;
  significant_up: number;
  significant_down: number;
  comparison: string;
}

interface TimelineMilestone {
  name: string;
  date: string;
}

interface TimelineEvent {
  id: string;
  name: string;
  start_date: string;
  end_date: string | null;
  category: string;
  status: string;
  progress: number;
  milestones: TimelineMilestone[];
  dependencies: string[];
}

interface TimelineData {
  events: TimelineEvent[];
  study_name: string;
  study_start: string;
  study_end: string | null;
  categories: string[];
}

// API functions
async function fetchForestPlotData(params: {
  effectMeasure?: string;
}): Promise<ForestPlotData> {
  const searchParams = new URLSearchParams();
  if (params.effectMeasure) searchParams.set("effect_measure", params.effectMeasure);

  const response = await fetch(`/api/v1/visualizations/forest?${searchParams.toString()}`);
  if (!response.ok) throw new Error("Failed to fetch forest plot data");
  return response.json();
}

async function fetchVolcanoData(params: {
  fcThreshold?: number;
  pThreshold?: number;
}): Promise<VolcanoData> {
  const searchParams = new URLSearchParams();
  if (params.fcThreshold) searchParams.set("fc_threshold", String(params.fcThreshold));
  if (params.pThreshold) searchParams.set("p_threshold", String(params.pThreshold));

  const response = await fetch(`/api/v1/visualizations/volcano?${searchParams.toString()}`);
  if (!response.ok) throw new Error("Failed to fetch volcano plot data");
  return response.json();
}

async function fetchTimelineData(): Promise<TimelineData> {
  const response = await fetch("/api/v1/visualizations/timeline");
  if (!response.ok) throw new Error("Failed to fetch timeline data");
  return response.json();
}

// Category colors for timeline
const CATEGORY_COLORS: Record<string, string> = {
  Planning: "#3b82f6",
  Regulatory: "#8b5cf6",
  Operations: "#f59e0b",
  Enrollment: "#10b981",
  Treatment: "#ef4444",
  "Follow-up": "#06b6d4",
  Analysis: "#ec4899",
  Publication: "#84cc16",
};

// Status colors
const STATUS_COLORS: Record<string, string> = {
  completed: "#10b981",
  in_progress: "#3b82f6",
  planned: "#6b7280",
  delayed: "#ef4444",
};

// ============================================================================
// Forest Plot Component
// ============================================================================

function ForestPlotTab() {
  const [effectMeasure, setEffectMeasure] = useState("OR");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["forest", effectMeasure],
    queryFn: () => fetchForestPlotData({ effectMeasure }),
  });

  const chartData = useMemo(() => {
    if (!data) return [];
    return data.studies.map((study, index) => ({
      name: study.study_name,
      year: study.year,
      effect: study.effect_size,
      ciLower: study.ci_lower,
      ciUpper: study.ci_upper,
      weight: study.weight,
      sampleSize: study.sample_size,
      index,
      errorBar: [study.effect_size - study.ci_lower, study.ci_upper - study.effect_size],
    }));
  }, [data]);

  const handleExport = useCallback(() => {
    const svgElement = document.querySelector(".forest-chart svg");
    if (!svgElement) return;
    const svgData = new XMLSerializer().serializeToString(svgElement);
    const blob = new Blob([svgData], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `forest-plot-${new Date().toISOString().split("T")[0]}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <Label className="text-sm">Effect Measure</Label>
            <Select value={effectMeasure} onValueChange={setEffectMeasure}>
              <SelectTrigger className="w-32 mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="OR">Odds Ratio</SelectItem>
                <SelectItem value="RR">Risk Ratio</SelectItem>
                <SelectItem value="HR">Hazard Ratio</SelectItem>
                <SelectItem value="MD">Mean Diff</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Forest Plot - Meta-Analysis</CardTitle>
          <CardDescription>
            {data ? `${data.studies.length} studies included` : "Loading..."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <AlertCircle className="h-8 w-8 mb-2" />
              <p>Failed to load forest plot data</p>
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-24">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : data ? (
            <div className="space-y-4">
              <div className="forest-chart">
                <ResponsiveContainer width="100%" height={400}>
                  <ComposedChart
                    data={chartData}
                    layout="vertical"
                    margin={{ top: 20, right: 80, bottom: 20, left: 150 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis
                      type="number"
                      domain={[0.3, 1.5]}
                      tickFormatter={(v) => v.toFixed(2)}
                    />
                    <YAxis type="category" dataKey="name" width={140} />
                    <RechartsTooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload;
                        return (
                          <div className="bg-popover border rounded-lg shadow-lg p-3 text-sm">
                            <div className="font-medium">{d.name} ({d.year})</div>
                            <div className="mt-1">
                              Effect: {d.effect.toFixed(2)} [{d.ciLower.toFixed(2)}, {d.ciUpper.toFixed(2)}]
                            </div>
                            <div className="text-muted-foreground">
                              Weight: {d.weight.toFixed(1)}% | N={d.sampleSize}
                            </div>
                          </div>
                        );
                      }}
                    />
                    <ReferenceLine x={data.null_value} stroke="#ef4444" strokeDasharray="3 3" />
                    <ReferenceLine x={data.pooled_effect} stroke="#10b981" strokeWidth={2} />
                    <Bar dataKey="effect" fill="#3b82f6" barSize={8}>
                      <ErrorBar dataKey="errorBar" stroke="#3b82f6" strokeWidth={1.5} />
                    </Bar>
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Summary */}
              <div className="grid gap-4 md:grid-cols-4">
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm text-muted-foreground">Pooled Effect</div>
                    <div className="text-2xl font-bold">{data.pooled_effect.toFixed(2)}</div>
                    <div className="text-xs text-muted-foreground">
                      [{data.pooled_ci_lower.toFixed(2)}, {data.pooled_ci_upper.toFixed(2)}]
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm text-muted-foreground">Heterogeneity (I2)</div>
                    <div className="text-2xl font-bold">{data.heterogeneity_i2.toFixed(1)}%</div>
                    <Badge variant={data.heterogeneity_i2 < 50 ? "default" : "destructive"} className="mt-1">
                      {data.heterogeneity_i2 < 25 ? "Low" : data.heterogeneity_i2 < 75 ? "Moderate" : "High"}
                    </Badge>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm text-muted-foreground">Q Statistic</div>
                    <div className="text-2xl font-bold">{data.heterogeneity_q.toFixed(2)}</div>
                    <div className="text-xs text-muted-foreground">
                      p = {data.heterogeneity_p.toFixed(3)}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm text-muted-foreground">Total Patients</div>
                    <div className="text-2xl font-bold">
                      {data.studies.reduce((sum, s) => sum + s.sample_size, 0).toLocaleString()}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {data.studies.length} studies
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// Volcano Plot Component
// ============================================================================

function VolcanoPlotTab() {
  const [fcThreshold, setFcThreshold] = useState(1.0);
  const [pThreshold, setPThreshold] = useState(0.05);
  const [showLabels, setShowLabels] = useState(true);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["volcano", fcThreshold, pThreshold],
    queryFn: () => fetchVolcanoData({ fcThreshold, pThreshold }),
  });

  const getPointColor = (point: VolcanoPoint) => {
    if (!point.significant) return "#9ca3af";
    return point.direction === "up" ? "#ef4444" : "#3b82f6";
  };

  const handleExport = useCallback(() => {
    const svgElement = document.querySelector(".volcano-chart svg");
    if (!svgElement) return;
    const svgData = new XMLSerializer().serializeToString(svgElement);
    const blob = new Blob([svgData], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `volcano-plot-${new Date().toISOString().split("T")[0]}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <Label className="text-sm">Fold Change Threshold</Label>
            <div className="mt-2 w-40">
              <Slider
                value={[fcThreshold]}
                onValueChange={([v]) => setFcThreshold(v)}
                min={0.5}
                max={2}
                step={0.1}
              />
              <div className="text-xs text-muted-foreground mt-1">|log2FC| &gt; {fcThreshold}</div>
            </div>
          </div>
          <div>
            <Label className="text-sm">P-value Threshold</Label>
            <Select value={String(pThreshold)} onValueChange={(v) => setPThreshold(Number(v))}>
              <SelectTrigger className="w-28 mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0.05">0.05</SelectItem>
                <SelectItem value="0.01">0.01</SelectItem>
                <SelectItem value="0.001">0.001</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Switch id="show-labels" checked={showLabels} onCheckedChange={setShowLabels} />
            <Label htmlFor="show-labels" className="text-sm">Show Labels</Label>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Volcano Plot - Differential Analysis</CardTitle>
          <CardDescription>
            {data ? `${data.comparison} - ${data.total_features} features` : "Loading..."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <AlertCircle className="h-8 w-8 mb-2" />
              <p>Failed to load volcano plot data</p>
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-24">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : data ? (
            <div className="space-y-4">
              <div className="volcano-chart">
                <ResponsiveContainer width="100%" height={450}>
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 40, left: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis
                      dataKey="log_fold_change"
                      type="number"
                      name="Log2 Fold Change"
                      domain={[-3, 3]}
                      label={{ value: "Log2 Fold Change", position: "bottom", offset: 20 }}
                    />
                    <YAxis
                      dataKey="neg_log_p_value"
                      type="number"
                      name="-Log10(p-value)"
                      domain={[0, 5]}
                      label={{ value: "-Log10(p-value)", angle: -90, position: "insideLeft" }}
                    />
                    <RechartsTooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload as VolcanoPoint;
                        return (
                          <div className="bg-popover border rounded-lg shadow-lg p-3 text-sm">
                            <div className="font-medium">{d.name}</div>
                            <div className="mt-1">FC: {Math.pow(2, d.log_fold_change).toFixed(2)}x</div>
                            <div>p-value: {d.p_value.toExponential(2)}</div>
                            {d.significant && (
                              <Badge className="mt-1" variant={d.direction === "up" ? "destructive" : "default"}>
                                {d.direction === "up" ? "Upregulated" : "Downregulated"}
                              </Badge>
                            )}
                          </div>
                        );
                      }}
                    />
                    {/* Threshold lines */}
                    <ReferenceLine x={-fcThreshold} stroke="#888" strokeDasharray="3 3" />
                    <ReferenceLine x={fcThreshold} stroke="#888" strokeDasharray="3 3" />
                    <ReferenceLine y={-Math.log10(pThreshold)} stroke="#888" strokeDasharray="3 3" />
                    <RechartsScatter data={data.points} shape="circle">
                      {data.points.map((point, index) => (
                        <Cell key={index} fill={getPointColor(point)} opacity={0.7} />
                      ))}
                    </RechartsScatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>

              {/* Summary */}
              <div className="grid gap-4 md:grid-cols-4">
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm text-muted-foreground">Total Features</div>
                    <div className="text-2xl font-bold">{data.total_features}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <TrendingUp className="h-4 w-4 text-red-500" />
                      Upregulated
                    </div>
                    <div className="text-2xl font-bold text-red-500">{data.significant_up}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <TrendingDown className="h-4 w-4 text-blue-500" />
                      Downregulated
                    </div>
                    <div className="text-2xl font-bold text-blue-500">{data.significant_down}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm text-muted-foreground">Not Significant</div>
                    <div className="text-2xl font-bold text-gray-500">
                      {data.total_features - data.significant_up - data.significant_down}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Significant features list */}
              {showLabels && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Significant Features</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <div className="text-xs font-medium text-red-500 mb-2">Upregulated</div>
                        <div className="space-y-1">
                          {data.points
                            .filter((p) => p.significant && p.direction === "up")
                            .slice(0, 5)
                            .map((p) => (
                              <div key={p.id} className="flex items-center justify-between text-sm">
                                <span>{p.name}</span>
                                <Badge variant="outline">{Math.pow(2, p.log_fold_change).toFixed(1)}x</Badge>
                              </div>
                            ))}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs font-medium text-blue-500 mb-2">Downregulated</div>
                        <div className="space-y-1">
                          {data.points
                            .filter((p) => p.significant && p.direction === "down")
                            .slice(0, 5)
                            .map((p) => (
                              <div key={p.id} className="flex items-center justify-between text-sm">
                                <span>{p.name}</span>
                                <Badge variant="outline">{Math.pow(2, p.log_fold_change).toFixed(2)}x</Badge>
                              </div>
                            ))}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// Timeline / Gantt Component
// ============================================================================

function TimelineTab() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["timeline"],
    queryFn: fetchTimelineData,
  });

  const handleExport = useCallback(() => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `study-timeline-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data]);

  // Calculate timeline scale
  const timelineScale = useMemo(() => {
    if (!data) return null;
    const start = new Date(data.study_start);
    const end = data.study_end ? new Date(data.study_end) : new Date();
    const totalDays = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
    return { start, end, totalDays };
  }, [data]);

  const getBarPosition = (startDate: string, endDate: string | null) => {
    if (!timelineScale || !endDate) return { left: 0, width: 0 };
    const start = new Date(startDate);
    const end = new Date(endDate);
    const startOffset = Math.ceil((start.getTime() - timelineScale.start.getTime()) / (1000 * 60 * 60 * 24));
    const duration = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
    return {
      left: (startOffset / timelineScale.totalDays) * 100,
      width: (duration / timelineScale.totalDays) * 100,
    };
  };

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">{data?.study_name || "Study Timeline"}</h3>
          <p className="text-sm text-muted-foreground">
            {data ? `${data.events.length} phases | ${data.categories.length} categories` : "Loading..."}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Timeline Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Study Timeline (Gantt Chart)</CardTitle>
          <CardDescription>
            {data && timelineScale
              ? `${timelineScale.start.toLocaleDateString()} - ${timelineScale.end.toLocaleDateString()}`
              : "Loading..."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <AlertCircle className="h-8 w-8 mb-2" />
              <p>Failed to load timeline data</p>
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-24">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : data && timelineScale ? (
            <div className="space-y-6">
              {/* Timeline header with months */}
              <div className="relative h-8 border-b">
                {Array.from({ length: Math.ceil(timelineScale.totalDays / 90) + 1 }).map((_, i) => {
                  const date = new Date(timelineScale.start);
                  date.setDate(date.getDate() + i * 90);
                  return (
                    <div
                      key={i}
                      className="absolute text-xs text-muted-foreground"
                      style={{ left: `${(i * 90 / timelineScale.totalDays) * 100}%` }}
                    >
                      {date.toLocaleDateString("en-US", { month: "short", year: "2-digit" })}
                    </div>
                  );
                })}
              </div>

              {/* Timeline bars */}
              <div className="space-y-4">
                {data.events.map((event) => {
                  const pos = getBarPosition(event.start_date, event.end_date);
                  return (
                    <div key={event.id} className="group">
                      <div className="flex items-center gap-4">
                        <div className="w-32 shrink-0">
                          <div className="text-sm font-medium truncate">{event.name}</div>
                          <div className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Badge
                              variant="outline"
                              className="h-5"
                              style={{
                                borderColor: CATEGORY_COLORS[event.category],
                                color: CATEGORY_COLORS[event.category],
                              }}
                            >
                              {event.category}
                            </Badge>
                          </div>
                        </div>
                        <div className="flex-1 relative h-8">
                          {/* Background track */}
                          <div className="absolute inset-0 bg-muted rounded" />
                          {/* Progress bar */}
                          <div
                            className="absolute h-full rounded transition-all"
                            style={{
                              left: `${pos.left}%`,
                              width: `${pos.width}%`,
                              backgroundColor: STATUS_COLORS[event.status],
                              opacity: 0.2,
                            }}
                          />
                          {/* Actual progress */}
                          <div
                            className="absolute h-full rounded transition-all"
                            style={{
                              left: `${pos.left}%`,
                              width: `${(pos.width * event.progress) / 100}%`,
                              backgroundColor: STATUS_COLORS[event.status],
                            }}
                          />
                          {/* Milestones */}
                          {event.milestones.map((milestone, i) => {
                            const milestoneDate = new Date(milestone.date);
                            const offset =
                              ((milestoneDate.getTime() - timelineScale.start.getTime()) /
                                (1000 * 60 * 60 * 24) /
                                timelineScale.totalDays) *
                              100;
                            return (
                              <TooltipProvider key={i}>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <div
                                      className="absolute w-3 h-3 bg-amber-500 rounded-full border-2 border-background cursor-pointer"
                                      style={{
                                        left: `${offset}%`,
                                        top: "50%",
                                        transform: "translate(-50%, -50%)",
                                      }}
                                    />
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p className="font-medium">{milestone.name}</p>
                                    <p className="text-xs text-muted-foreground">
                                      {new Date(milestone.date).toLocaleDateString()}
                                    </p>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            );
                          })}
                        </div>
                        <div className="w-20 shrink-0 text-right">
                          <div className="text-sm font-medium">{event.progress}%</div>
                          <Badge
                            variant="outline"
                            className="text-xs"
                            style={{ borderColor: STATUS_COLORS[event.status] }}
                          >
                            {event.status === "in_progress" ? (
                              <Clock className="h-3 w-3 mr-1" />
                            ) : event.status === "completed" ? (
                              <CheckCircle className="h-3 w-3 mr-1" />
                            ) : null}
                            {event.status.replace("_", " ")}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Legend */}
              <div className="flex flex-wrap gap-4 pt-4 border-t">
                <div className="text-sm font-medium text-muted-foreground">Categories:</div>
                {data.categories.map((cat) => (
                  <div key={cat} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded"
                      style={{ backgroundColor: CATEGORY_COLORS[cat] }}
                    />
                    <span className="text-sm">{cat}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// Main Page Component
// ============================================================================

export default function ResearchPlotsPage() {
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/analytics/visualizations">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Microscope className="h-6 w-6" />
              Research Plots
            </h1>
            <p className="text-muted-foreground">
              Meta-analysis, differential analysis, and study timeline visualizations
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="forest" className="space-y-6">
        <TabsList>
          <TabsTrigger value="forest" className="gap-2">
            <BarChart2 className="h-4 w-4" />
            Forest Plot
          </TabsTrigger>
          <TabsTrigger value="volcano" className="gap-2">
            <Circle className="h-4 w-4" />
            Volcano Plot
          </TabsTrigger>
          <TabsTrigger value="timeline" className="gap-2">
            <Calendar className="h-4 w-4" />
            Study Timeline
          </TabsTrigger>
        </TabsList>

        <TabsContent value="forest">
          <ForestPlotTab />
        </TabsContent>

        <TabsContent value="volcano">
          <VolcanoPlotTab />
        </TabsContent>

        <TabsContent value="timeline">
          <TimelineTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
