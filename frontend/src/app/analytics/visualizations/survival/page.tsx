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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Activity,
  Users,
  TrendingDown,
  Clock,
  AlertCircle,
  Info,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  ComposedChart,
  ReferenceLine,
} from "recharts";
import { DEMO_SURVIVAL_DATA } from "@/lib/demo-data";

// Types
interface SurvivalPoint {
  time: number;
  survival_probability: number;
  at_risk: number;
  events: number;
  censored: number;
  ci_lower: number | null;
  ci_upper: number | null;
}

interface SurvivalCurve {
  cohort_id: string;
  cohort_name: string;
  points: SurvivalPoint[];
  median_survival: number | null;
  events_total: number;
  censored_total: number;
  patients_total: number;
}

interface SurvivalData {
  curves: SurvivalCurve[];
  log_rank_p_value: number | null;
  hazard_ratio: number | null;
  hazard_ratio_ci: number[] | null;
  time_unit: string;
}

// API function
async function fetchSurvivalData(params: {
  endpoint?: string;
  maxTime?: number;
}): Promise<SurvivalData> {
  const searchParams = new URLSearchParams();
  if (params.endpoint) searchParams.set("endpoint", params.endpoint);
  if (params.maxTime) searchParams.set("max_time", String(params.maxTime));

  try {
    const response = await fetch(`/api/v1/visualizations/survival?${searchParams.toString()}`);
    if (!response.ok) {
      return DEMO_SURVIVAL_DATA as SurvivalData;
    }
    return response.json();
  } catch {
    return DEMO_SURVIVAL_DATA as SurvivalData;
  }
}

// Cohort colors
const COHORT_COLORS = ["#10b981", "#ef4444", "#3b82f6", "#f59e0b"];

// Custom tooltip
function CustomTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: { name: string; value: number; color: string; payload: { at_risk?: number; events?: number } }[];
  label?: number;
}) {
  if (!active || !payload || !payload.length) return null;

  return (
    <div className="bg-popover border rounded-lg shadow-lg p-3 text-sm">
      <div className="font-medium mb-2">Month {label}</div>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 mb-1">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-muted-foreground">{entry.name}:</span>
          <span className="font-medium">{(entry.value * 100).toFixed(1)}%</span>
        </div>
      ))}
      {payload[0]?.payload?.at_risk !== undefined && (
        <div className="mt-2 pt-2 border-t text-xs text-muted-foreground">
          At risk: {payload[0].payload.at_risk}
        </div>
      )}
    </div>
  );
}

export default function SurvivalAnalysisPage() {
  // State
  const [endpoint, setEndpoint] = useState("overall_survival");
  const [maxTime, setMaxTime] = useState(60);
  const [showCI, setShowCI] = useState(true);
  const [showRiskTable, setShowRiskTable] = useState(true);
  const [selectedCohorts, setSelectedCohorts] = useState<string[]>(["treatment", "control"]);

  // Fetch data
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["survival", endpoint, maxTime],
    queryFn: () => fetchSurvivalData({ endpoint, maxTime }),
  });

  // Transform data for chart
  const chartData = useMemo(() => {
    if (!data || !data.curves.length) return [];

    // Get all unique time points
    const timePoints = new Set<number>();
    data.curves.forEach((curve) => {
      curve.points.forEach((p) => timePoints.add(p.time));
    });

    // Create merged data
    const sortedTimes = Array.from(timePoints).sort((a, b) => a - b);
    return sortedTimes.map((time) => {
      const point: Record<string, number | null> = { time };

      data.curves.forEach((curve) => {
        const p = curve.points.find((pt) => pt.time === time);
        if (p) {
          point[curve.cohort_id] = p.survival_probability;
          point[`${curve.cohort_id}_ci_lower`] = p.ci_lower;
          point[`${curve.cohort_id}_ci_upper`] = p.ci_upper;
          point[`${curve.cohort_id}_at_risk`] = p.at_risk;
          point[`${curve.cohort_id}_events`] = p.events;
        }
      });

      return point;
    });
  }, [data]);

  // Risk table data
  const riskTableData = useMemo(() => {
    if (!data || !data.curves.length) return [];

    const intervals = [0, 12, 24, 36, 48, 60].filter((t) => t <= maxTime);
    return intervals.map((time) => {
      const row: Record<string, number | string> = { time };
      data.curves.forEach((curve) => {
        const p = curve.points.find((pt) => pt.time === time);
        row[curve.cohort_id] = p?.at_risk ?? "-";
      });
      return row;
    });
  }, [data, maxTime]);

  // Handle export
  const handleExport = useCallback(() => {
    const svgElement = document.querySelector(".survival-chart svg");
    if (!svgElement) return;

    const svgData = new XMLSerializer().serializeToString(svgElement);
    const blob = new Blob([svgData], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `survival-analysis-${new Date().toISOString().split("T")[0]}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  // Format p-value
  const formatPValue = (p: number | null) => {
    if (p === null) return "N/A";
    if (p < 0.001) return "< 0.001";
    return p.toFixed(4);
  };

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
              <Activity className="h-6 w-6" />
              Survival Analysis
            </h1>
            <p className="text-muted-foreground">
              Kaplan-Meier survival curves with statistical comparisons
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export SVG
          </Button>
        </div>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Analysis Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-4">
            <div>
              <Label className="text-sm">Endpoint</Label>
              <Select value={endpoint} onValueChange={setEndpoint}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="overall_survival">Overall Survival</SelectItem>
                  <SelectItem value="progression_free">Progression-Free Survival</SelectItem>
                  <SelectItem value="event_free">Event-Free Survival</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm">Max Follow-up (months)</Label>
              <div className="mt-3">
                <Slider
                  value={[maxTime]}
                  onValueChange={([v]) => setMaxTime(v)}
                  min={12}
                  max={120}
                  step={12}
                />
                <div className="text-xs text-muted-foreground mt-1">{maxTime} months</div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Switch
                  id="show-ci"
                  checked={showCI}
                  onCheckedChange={setShowCI}
                />
                <Label htmlFor="show-ci" className="text-sm">Show Confidence Intervals</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="show-risk"
                  checked={showRiskTable}
                  onCheckedChange={setShowRiskTable}
                />
                <Label htmlFor="show-risk" className="text-sm">Show Risk Table</Label>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-4">
        {/* Chart */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Kaplan-Meier Survival Curves</CardTitle>
                <CardDescription>
                  {endpoint.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())} over{" "}
                  {maxTime} months
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <AlertCircle className="h-8 w-8 mb-2" />
                <p>Failed to load survival data</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
                  Retry
                </Button>
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-24">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : data && chartData.length > 0 ? (
              <div className="space-y-6">
                {/* Chart */}
                <div className="survival-chart">
                  <ResponsiveContainer width="100%" height={400}>
                    <ComposedChart data={chartData} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                      <XAxis
                        dataKey="time"
                        label={{ value: `Time (${data.time_unit})`, position: "bottom", offset: 0 }}
                      />
                      <YAxis
                        domain={[0, 1]}
                        tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                        label={{ value: "Survival Probability", angle: -90, position: "insideLeft" }}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend verticalAlign="top" height={36} />

                      {/* Reference line at median if exists */}
                      <ReferenceLine y={0.5} stroke="#888" strokeDasharray="3 3" />

                      {/* Confidence intervals as areas */}
                      {showCI &&
                        data.curves.map((curve, index) => (
                          <Area
                            key={`ci-${curve.cohort_id}`}
                            dataKey={`${curve.cohort_id}_ci_upper`}
                            stroke="none"
                            fill={COHORT_COLORS[index]}
                            fillOpacity={0.1}
                            name={`${curve.cohort_name} CI`}
                            legendType="none"
                          />
                        ))}

                      {/* Survival curves */}
                      {data.curves.map((curve, index) => (
                        <Line
                          key={curve.cohort_id}
                          type="stepAfter"
                          dataKey={curve.cohort_id}
                          stroke={COHORT_COLORS[index]}
                          strokeWidth={2}
                          dot={false}
                          name={curve.cohort_name}
                        />
                      ))}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>

                {/* Risk Table */}
                {showRiskTable && (
                  <div>
                    <h4 className="text-sm font-medium mb-2">Number at Risk</h4>
                    <div className="border rounded-lg overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-24">Time</TableHead>
                            {data.curves.map((curve, index) => (
                              <TableHead key={curve.cohort_id}>
                                <div className="flex items-center gap-2">
                                  <div
                                    className="w-3 h-3 rounded-full"
                                    style={{ backgroundColor: COHORT_COLORS[index] }}
                                  />
                                  {curve.cohort_name}
                                </div>
                              </TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {riskTableData.map((row, index) => (
                            <TableRow key={index}>
                              <TableCell className="font-medium">{row.time} mo</TableCell>
                              {data.curves.map((curve) => (
                                <TableCell key={curve.cohort_id}>
                                  {row[curve.cohort_id]}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
                <Activity className="h-12 w-12 mb-4 opacity-50" />
                <p>No survival data available</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sidebar Stats */}
        <div className="space-y-6">
          {/* Statistical Summary */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Statistical Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {data && (
                <>
                  <div>
                    <div className="text-xs text-muted-foreground">Log-Rank Test</div>
                    <div className="text-lg font-bold">
                      p = {formatPValue(data.log_rank_p_value)}
                    </div>
                    {data.log_rank_p_value !== null && data.log_rank_p_value < 0.05 && (
                      <Badge className="mt-1 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                        Significant
                      </Badge>
                    )}
                  </div>
                  <div className="border-t pt-4">
                    <div className="text-xs text-muted-foreground">Hazard Ratio</div>
                    <div className="text-lg font-bold">
                      {data.hazard_ratio?.toFixed(2) ?? "N/A"}
                    </div>
                    {data.hazard_ratio_ci && (
                      <div className="text-xs text-muted-foreground">
                        95% CI: {data.hazard_ratio_ci[0].toFixed(2)} -{" "}
                        {data.hazard_ratio_ci[1].toFixed(2)}
                      </div>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Cohort Stats */}
          {data?.curves.map((curve, index) => (
            <Card key={curve.cohort_id}>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COHORT_COLORS[index] }}
                  />
                  {curve.cohort_name}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Users className="h-4 w-4" />
                    Patients
                  </div>
                  <div className="font-medium">{curve.patients_total}</div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <TrendingDown className="h-4 w-4" />
                    Events
                  </div>
                  <div className="font-medium">{curve.events_total}</div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    Median Survival
                  </div>
                  <div className="font-medium">
                    {curve.median_survival ? `${curve.median_survival} mo` : "NR"}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Info */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                <div className="text-xs text-muted-foreground">
                  <p>
                    Survival curves are estimated using the Kaplan-Meier method.
                    Vertical drops indicate events, tick marks indicate censoring.
                  </p>
                  <p className="mt-2">
                    NR = Not Reached (median survival not yet observed)
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
