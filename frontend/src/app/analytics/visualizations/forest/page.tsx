"use client";

import { useState, useMemo } from "react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  BarChart2,
  Info,
  Square,
  Diamond,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Settings,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface StudyResult {
  id: string;
  study: string;
  year: number;
  n_treatment: number;
  n_control: number;
  effect_size: number; // e.g., odds ratio, risk ratio, hazard ratio
  ci_lower: number;
  ci_upper: number;
  weight: number; // percentage weight in meta-analysis
  se: number;
  pvalue?: number;
  subgroup?: string;
}

interface MetaAnalysisResult {
  studies: StudyResult[];
  pooled_effect: number;
  pooled_ci_lower: number;
  pooled_ci_upper: number;
  pooled_pvalue: number;
  i_squared: number;
  tau_squared: number;
  q_statistic: number;
  q_pvalue: number;
  model: "fixed" | "random";
  effect_measure: string;
}

// ============================================================================
// Mock Data
// ============================================================================

const mockMetaAnalysis: MetaAnalysisResult = {
  studies: [
    { id: "1", study: "Anderson 2018", year: 2018, n_treatment: 245, n_control: 248, effect_size: 0.72, ci_lower: 0.52, ci_upper: 0.99, weight: 12.4, se: 0.165, pvalue: 0.045, subgroup: "North America" },
    { id: "2", study: "Baker 2019", year: 2019, n_treatment: 512, n_control: 508, effect_size: 0.65, ci_lower: 0.51, ci_upper: 0.83, weight: 18.2, se: 0.124, pvalue: 0.001, subgroup: "Europe" },
    { id: "3", study: "Chen 2019", year: 2019, n_treatment: 178, n_control: 182, effect_size: 0.89, ci_lower: 0.58, ci_upper: 1.37, weight: 8.5, se: 0.219, pvalue: 0.592, subgroup: "Asia" },
    { id: "4", study: "Davis 2020", year: 2020, n_treatment: 423, n_control: 419, effect_size: 0.58, ci_lower: 0.44, ci_upper: 0.76, weight: 16.8, se: 0.138, pvalue: 0.001, subgroup: "North America" },
    { id: "5", study: "Evans 2020", year: 2020, n_treatment: 156, n_control: 161, effect_size: 0.78, ci_lower: 0.48, ci_upper: 1.27, weight: 7.2, se: 0.248, pvalue: 0.314, subgroup: "Europe" },
    { id: "6", study: "Fischer 2021", year: 2021, n_treatment: 298, n_control: 302, effect_size: 0.61, ci_lower: 0.43, ci_upper: 0.86, weight: 13.1, se: 0.175, pvalue: 0.005, subgroup: "Europe" },
    { id: "7", study: "Garcia 2021", year: 2021, n_treatment: 189, n_control: 194, effect_size: 0.82, ci_lower: 0.54, ci_upper: 1.24, weight: 9.1, se: 0.211, pvalue: 0.348, subgroup: "South America" },
    { id: "8", study: "Harris 2022", year: 2022, n_treatment: 367, n_control: 371, effect_size: 0.69, ci_lower: 0.51, ci_upper: 0.93, weight: 14.7, se: 0.154, pvalue: 0.015, subgroup: "North America" },
  ],
  pooled_effect: 0.68,
  pooled_ci_lower: 0.59,
  pooled_ci_upper: 0.78,
  pooled_pvalue: 0.001,
  i_squared: 28.4,
  tau_squared: 0.012,
  q_statistic: 9.78,
  q_pvalue: 0.202,
  model: "random",
  effect_measure: "Odds Ratio",
};

// ============================================================================
// Helper Functions
// ============================================================================

const formatCI = (effect: number, lower: number, upper: number) => {
  return `${effect.toFixed(2)} [${lower.toFixed(2)}, ${upper.toFixed(2)}]`;
};

const getHeterogeneityInterpretation = (iSquared: number) => {
  if (iSquared < 25) return { level: "Low", color: "text-green-600" };
  if (iSquared < 50) return { level: "Moderate", color: "text-amber-600" };
  if (iSquared < 75) return { level: "Substantial", color: "text-orange-600" };
  return { level: "Considerable", color: "text-red-600" };
};

// ============================================================================
// Forest Plot SVG Component
// ============================================================================

function ForestPlotSVG({ data, showSubgroups }: { data: MetaAnalysisResult; showSubgroups: boolean }) {
  // Layout constants
  const margin = { top: 40, right: 180, bottom: 60, left: 200 };
  const rowHeight = 28;
  const plotWidth = 400;
  const width = margin.left + plotWidth + margin.right;
  const height = margin.top + (data.studies.length + 2) * rowHeight + margin.bottom;

  // Calculate x-axis scale (log scale for ratios)
  const minEffect = Math.min(...data.studies.map(s => s.ci_lower), data.pooled_ci_lower);
  const maxEffect = Math.max(...data.studies.map(s => s.ci_upper), data.pooled_ci_upper);
  const xMin = Math.max(0.1, minEffect * 0.8);
  const xMax = maxEffect * 1.2;

  const logScale = (value: number) => {
    const logMin = Math.log(xMin);
    const logMax = Math.log(xMax);
    return margin.left + ((Math.log(value) - logMin) / (logMax - logMin)) * plotWidth;
  };

  const xTicks = [0.25, 0.5, 1, 2, 4].filter(t => t >= xMin && t <= xMax);

  // Calculate square size based on weight
  const maxWeight = Math.max(...data.studies.map(s => s.weight));
  const getSquareSize = (weight: number) => 6 + (weight / maxWeight) * 10;

  return (
    <svg width={width} height={height} className="overflow-visible">
      {/* Background grid */}
      <g>
        {xTicks.map((tick) => (
          <line
            key={tick}
            x1={logScale(tick)}
            y1={margin.top}
            x2={logScale(tick)}
            y2={height - margin.bottom}
            stroke="#e5e7eb"
            strokeDasharray={tick === 1 ? "none" : "4,4"}
            strokeWidth={tick === 1 ? 2 : 1}
          />
        ))}
      </g>

      {/* X-axis */}
      <g transform={`translate(0, ${height - margin.bottom})`}>
        <line
          x1={margin.left}
          y1={0}
          x2={margin.left + plotWidth}
          y2={0}
          stroke="#374151"
          strokeWidth={1}
        />
        {xTicks.map((tick) => (
          <g key={tick} transform={`translate(${logScale(tick)}, 0)`}>
            <line y2={6} stroke="#374151" />
            <text
              y={20}
              textAnchor="middle"
              className="text-xs fill-current text-muted-foreground"
            >
              {tick}
            </text>
          </g>
        ))}
        <text
          x={margin.left + plotWidth / 2}
          y={45}
          textAnchor="middle"
          className="text-sm fill-current"
        >
          {data.effect_measure} (95% CI)
        </text>
      </g>

      {/* Favor labels */}
      <text
        x={logScale(0.5)}
        y={height - 15}
        textAnchor="middle"
        className="text-xs fill-current text-muted-foreground"
      >
        Favors Treatment
      </text>
      <text
        x={logScale(2)}
        y={height - 15}
        textAnchor="middle"
        className="text-xs fill-current text-muted-foreground"
      >
        Favors Control
      </text>

      {/* Header */}
      <g transform={`translate(0, ${margin.top - 10})`}>
        <text x={10} className="text-xs font-medium fill-current">Study</text>
        <text x={margin.left + plotWidth / 2} textAnchor="middle" className="text-xs font-medium fill-current">
          Effect Size
        </text>
        <text x={width - margin.right + 10} className="text-xs font-medium fill-current">OR [95% CI]</text>
        <text x={width - 50} className="text-xs font-medium fill-current">Weight</text>
      </g>

      {/* Individual studies */}
      {data.studies.map((study, i) => {
        const y = margin.top + (i + 1) * rowHeight;
        const squareSize = getSquareSize(study.weight);
        const effectX = logScale(study.effect_size);
        const ciLowerX = logScale(study.ci_lower);
        const ciUpperX = logScale(study.ci_upper);

        return (
          <g key={study.id} transform={`translate(0, ${y})`}>
            {/* Study name */}
            <text x={10} y={4} className="text-xs fill-current">
              {study.study}
            </text>

            {/* Subgroup indicator */}
            {showSubgroups && study.subgroup && (
              <text x={150} y={4} className="text-xs fill-current text-muted-foreground">
                ({study.subgroup})
              </text>
            )}

            {/* Confidence interval line */}
            <line
              x1={ciLowerX}
              y1={0}
              x2={ciUpperX}
              y2={0}
              stroke="#3b82f6"
              strokeWidth={1.5}
            />

            {/* Effect size square */}
            <rect
              x={effectX - squareSize / 2}
              y={-squareSize / 2}
              width={squareSize}
              height={squareSize}
              fill="#3b82f6"
              className="transition-all hover:fill-blue-700"
            />

            {/* CI whiskers */}
            <line x1={ciLowerX} y1={-4} x2={ciLowerX} y2={4} stroke="#3b82f6" strokeWidth={1.5} />
            <line x1={ciUpperX} y1={-4} x2={ciUpperX} y2={4} stroke="#3b82f6" strokeWidth={1.5} />

            {/* Effect estimate text */}
            <text x={width - margin.right + 10} y={4} className="text-xs fill-current font-mono">
              {formatCI(study.effect_size, study.ci_lower, study.ci_upper)}
            </text>

            {/* Weight */}
            <text x={width - 50} y={4} className="text-xs fill-current">
              {study.weight.toFixed(1)}%
            </text>
          </g>
        );
      })}

      {/* Pooled effect (diamond) */}
      <g transform={`translate(0, ${margin.top + (data.studies.length + 1) * rowHeight})`}>
        {/* Separator line */}
        <line
          x1={margin.left}
          y1={-10}
          x2={width - margin.right}
          y2={-10}
          stroke="#374151"
          strokeWidth={1}
        />

        {/* Label */}
        <text x={10} y={4} className="text-xs font-medium fill-current">
          Overall ({data.model === "random" ? "Random" : "Fixed"} Effects)
        </text>

        {/* Diamond */}
        <polygon
          points={`
            ${logScale(data.pooled_ci_lower)},0
            ${logScale(data.pooled_effect)},-8
            ${logScale(data.pooled_ci_upper)},0
            ${logScale(data.pooled_effect)},8
          `}
          fill="#ef4444"
          className="transition-all hover:fill-red-700"
        />

        {/* Effect estimate text */}
        <text x={width - margin.right + 10} y={4} className="text-xs fill-current font-mono font-medium">
          {formatCI(data.pooled_effect, data.pooled_ci_lower, data.pooled_ci_upper)}
        </text>

        {/* Weight */}
        <text x={width - 50} y={4} className="text-xs fill-current font-medium">
          100%
        </text>
      </g>
    </svg>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function ForestPlotPage() {
  const [data] = useState<MetaAnalysisResult>(mockMetaAnalysis);
  const [showSubgroups, setShowSubgroups] = useState(false);
  const [sortBy, setSortBy] = useState<"year" | "effect" | "weight">("year");

  // Sort studies
  const sortedData = useMemo(() => {
    const sorted = [...data.studies].sort((a, b) => {
      switch (sortBy) {
        case "year":
          return a.year - b.year;
        case "effect":
          return a.effect_size - b.effect_size;
        case "weight":
          return b.weight - a.weight;
        default:
          return 0;
      }
    });
    return { ...data, studies: sorted };
  }, [data, sortBy]);

  const heterogeneity = getHeterogeneityInterpretation(data.i_squared);

  // Summary stats
  const totalN = data.studies.reduce((sum, s) => sum + s.n_treatment + s.n_control, 0);
  const significantStudies = data.studies.filter(s => s.pvalue && s.pvalue < 0.05).length;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/analytics/visualizations/research">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Research
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Forest Plot</h1>
            <p className="text-muted-foreground">
              Meta-analysis visualization with pooled effect estimates
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Summary Statistics */}
      <div className="grid gap-4 md:grid-cols-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Studies</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.studies.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total N</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalN.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Pooled {data.effect_measure}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.pooled_effect.toFixed(2)}</div>
            <div className="text-xs text-muted-foreground">
              95% CI: [{data.pooled_ci_lower.toFixed(2)}, {data.pooled_ci_upper.toFixed(2)}]
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">p-value</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${data.pooled_pvalue < 0.05 ? "text-green-600" : ""}`}>
              {data.pooled_pvalue < 0.001 ? "<0.001" : data.pooled_pvalue.toFixed(3)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">I² Heterogeneity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${heterogeneity.color}`}>
              {data.i_squared.toFixed(1)}%
            </div>
            <div className="text-xs text-muted-foreground">{heterogeneity.level}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Significant Studies</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {significantStudies}/{data.studies.length}
            </div>
            <div className="text-xs text-muted-foreground">p &lt; 0.05</div>
          </CardContent>
        </Card>
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-2">
              <Label>Sort by:</Label>
              <Select value={sortBy} onValueChange={(v) => setSortBy(v as typeof sortBy)}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="year">Year</SelectItem>
                  <SelectItem value="effect">Effect Size</SelectItem>
                  <SelectItem value="weight">Weight</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="subgroups"
                checked={showSubgroups}
                onCheckedChange={(c) => setShowSubgroups(c === true)}
              />
              <Label htmlFor="subgroups">Show Subgroups</Label>
            </div>
            <Badge variant="outline">
              Model: {data.model === "random" ? "Random Effects" : "Fixed Effects"}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Forest Plot */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart2 className="h-5 w-5" />
            Forest Plot
          </CardTitle>
          <CardDescription>
            Individual study effects and pooled estimate
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <ForestPlotSVG data={sortedData} showSubgroups={showSubgroups} />
        </CardContent>
      </Card>

      {/* Study Details Table */}
      <Card>
        <CardHeader>
          <CardTitle>Study Details</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Study</TableHead>
                <TableHead>Year</TableHead>
                <TableHead className="text-right">N Treatment</TableHead>
                <TableHead className="text-right">N Control</TableHead>
                <TableHead className="text-right">{data.effect_measure}</TableHead>
                <TableHead className="text-right">95% CI</TableHead>
                <TableHead className="text-right">p-value</TableHead>
                <TableHead className="text-right">Weight</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedData.studies.map((study) => (
                <TableRow key={study.id}>
                  <TableCell className="font-medium">{study.study}</TableCell>
                  <TableCell>{study.year}</TableCell>
                  <TableCell className="text-right">{study.n_treatment}</TableCell>
                  <TableCell className="text-right">{study.n_control}</TableCell>
                  <TableCell className="text-right font-mono">{study.effect_size.toFixed(2)}</TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">
                    [{study.ci_lower.toFixed(2)}, {study.ci_upper.toFixed(2)}]
                  </TableCell>
                  <TableCell className="text-right">
                    <span className={study.pvalue && study.pvalue < 0.05 ? "font-medium text-green-600" : ""}>
                      {study.pvalue ? study.pvalue.toFixed(3) : "-"}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">{study.weight.toFixed(1)}%</TableCell>
                </TableRow>
              ))}
              {/* Pooled row */}
              <TableRow className="font-medium bg-muted/50">
                <TableCell colSpan={2}>Overall ({data.model} effects)</TableCell>
                <TableCell className="text-right">
                  {data.studies.reduce((sum, s) => sum + s.n_treatment, 0)}
                </TableCell>
                <TableCell className="text-right">
                  {data.studies.reduce((sum, s) => sum + s.n_control, 0)}
                </TableCell>
                <TableCell className="text-right font-mono">{data.pooled_effect.toFixed(2)}</TableCell>
                <TableCell className="text-right font-mono">
                  [{data.pooled_ci_lower.toFixed(2)}, {data.pooled_ci_upper.toFixed(2)}]
                </TableCell>
                <TableCell className="text-right">
                  <span className={data.pooled_pvalue < 0.05 ? "text-green-600" : ""}>
                    {data.pooled_pvalue < 0.001 ? "<0.001" : data.pooled_pvalue.toFixed(3)}
                  </span>
                </TableCell>
                <TableCell className="text-right">100%</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Heterogeneity Analysis */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            Heterogeneity Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="p-4 rounded-lg border">
              <div className="text-sm text-muted-foreground">I² (Inconsistency)</div>
              <div className={`text-2xl font-bold ${heterogeneity.color}`}>
                {data.i_squared.toFixed(1)}%
              </div>
              <div className="text-sm mt-1">{heterogeneity.level} heterogeneity</div>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="text-sm text-muted-foreground">τ² (Between-study variance)</div>
              <div className="text-2xl font-bold">{data.tau_squared.toFixed(4)}</div>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="text-sm text-muted-foreground">Q-statistic (Cochran&apos;s Q)</div>
              <div className="text-2xl font-bold">{data.q_statistic.toFixed(2)}</div>
              <div className="text-sm mt-1">p = {data.q_pvalue.toFixed(3)}</div>
            </div>
          </div>

          <div className="mt-4 p-4 rounded-lg bg-muted">
            <h4 className="font-medium mb-2">Interpretation</h4>
            <p className="text-sm text-muted-foreground">
              The I² statistic of {data.i_squared.toFixed(1)}% indicates {heterogeneity.level.toLowerCase()} heterogeneity
              between studies. {data.i_squared < 50
                ? "The variation in study results is likely due to chance rather than true differences between studies."
                : "Consider exploring sources of heterogeneity through subgroup analysis or meta-regression."}
              The pooled effect estimate of {data.pooled_effect.toFixed(2)} ({data.effect_measure}) suggests
              {data.pooled_effect < 1
                ? " a protective effect of the treatment"
                : " an increased risk with treatment"}.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
