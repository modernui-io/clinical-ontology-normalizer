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
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Target,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

interface MeasureDataPoint {
  month: string;
  value: number;
}

interface QualityMeasure {
  id: string;
  name: string;
  measure_id: string;
  category: string;
  description: string;
  current_rate: number;
  target_rate: number;
  benchmark_rate: number;
  trend: "up" | "down" | "flat";
  trend_pct: number;
  data: MeasureDataPoint[];
  numerator: number;
  denominator: number;
}

const mockMeasures: QualityMeasure[] = [
  {
    id: "1", name: "Diabetes HbA1c Control", measure_id: "NQF-0059",
    category: "Diabetes", description: "Percentage of patients with diabetes aged 18-75 whose HbA1c was <8%",
    current_rate: 72.4, target_rate: 80, benchmark_rate: 78.5,
    trend: "up", trend_pct: 3.2, numerator: 892, denominator: 1232,
    data: [
      { month: "Jul", value: 68.1 }, { month: "Aug", value: 69.3 },
      { month: "Sep", value: 70.0 }, { month: "Oct", value: 70.8 },
      { month: "Nov", value: 71.5 }, { month: "Dec", value: 72.4 },
    ],
  },
  {
    id: "2", name: "Hypertension Control", measure_id: "NQF-0018",
    category: "Cardiovascular", description: "Percentage of patients with hypertension whose BP was <140/90",
    current_rate: 68.9, target_rate: 75, benchmark_rate: 72.0,
    trend: "up", trend_pct: 1.8, numerator: 1456, denominator: 2113,
    data: [
      { month: "Jul", value: 65.5 }, { month: "Aug", value: 66.2 },
      { month: "Sep", value: 67.0 }, { month: "Oct", value: 67.8 },
      { month: "Nov", value: 68.4 }, { month: "Dec", value: 68.9 },
    ],
  },
  {
    id: "3", name: "Breast Cancer Screening", measure_id: "NQF-2372",
    category: "Prevention", description: "Women 50-74 who had a mammogram in the past 27 months",
    current_rate: 78.2, target_rate: 82, benchmark_rate: 80.1,
    trend: "up", trend_pct: 2.5, numerator: 645, denominator: 825,
    data: [
      { month: "Jul", value: 74.8 }, { month: "Aug", value: 75.6 },
      { month: "Sep", value: 76.3 }, { month: "Oct", value: 77.1 },
      { month: "Nov", value: 77.8 }, { month: "Dec", value: 78.2 },
    ],
  },
  {
    id: "4", name: "Depression Screening", measure_id: "NQF-0418",
    category: "Behavioral Health", description: "Patients aged 12+ screened for depression with PHQ-9",
    current_rate: 55.3, target_rate: 70, benchmark_rate: 62.0,
    trend: "down", trend_pct: -1.2, numerator: 1108, denominator: 2004,
    data: [
      { month: "Jul", value: 58.2 }, { month: "Aug", value: 57.5 },
      { month: "Sep", value: 56.8 }, { month: "Oct", value: 56.2 },
      { month: "Nov", value: 55.8 }, { month: "Dec", value: 55.3 },
    ],
  },
  {
    id: "5", name: "Colorectal Cancer Screening", measure_id: "NQF-0034",
    category: "Prevention", description: "Adults 45-75 appropriately screened for colorectal cancer",
    current_rate: 62.1, target_rate: 72, benchmark_rate: 68.5,
    trend: "up", trend_pct: 4.1, numerator: 534, denominator: 860,
    data: [
      { month: "Jul", value: 56.2 }, { month: "Aug", value: 57.8 },
      { month: "Sep", value: 59.0 }, { month: "Oct", value: 60.2 },
      { month: "Nov", value: 61.3 }, { month: "Dec", value: 62.1 },
    ],
  },
  {
    id: "6", name: "Statin Therapy (ASCVD)", measure_id: "NQF-0543",
    category: "Cardiovascular", description: "Patients with ASCVD on high-intensity statin therapy",
    current_rate: 81.5, target_rate: 85, benchmark_rate: 82.0,
    trend: "flat", trend_pct: 0.3, numerator: 489, denominator: 600,
    data: [
      { month: "Jul", value: 80.8 }, { month: "Aug", value: 81.0 },
      { month: "Sep", value: 81.1 }, { month: "Oct", value: 81.2 },
      { month: "Nov", value: 81.3 }, { month: "Dec", value: 81.5 },
    ],
  },
  {
    id: "7", name: "Medication Reconciliation", measure_id: "NQF-0097",
    category: "Care Coordination", description: "Patients with medication reconciliation post-discharge",
    current_rate: 74.8, target_rate: 85, benchmark_rate: 78.0,
    trend: "up", trend_pct: 5.2, numerator: 318, denominator: 425,
    data: [
      { month: "Jul", value: 68.0 }, { month: "Aug", value: 69.5 },
      { month: "Sep", value: 71.2 }, { month: "Oct", value: 72.5 },
      { month: "Nov", value: 73.8 }, { month: "Dec", value: 74.8 },
    ],
  },
  {
    id: "8", name: "Falls Risk Assessment", measure_id: "NQF-0101",
    category: "Safety", description: "Patients 65+ with documented falls risk assessment",
    current_rate: 88.2, target_rate: 90, benchmark_rate: 85.0,
    trend: "up", trend_pct: 1.0, numerator: 712, denominator: 807,
    data: [
      { month: "Jul", value: 86.5 }, { month: "Aug", value: 87.0 },
      { month: "Sep", value: 87.3 }, { month: "Oct", value: 87.7 },
      { month: "Nov", value: 88.0 }, { month: "Dec", value: 88.2 },
    ],
  },
];

const categories = [...new Set(mockMeasures.map((m) => m.category))];

function TrendChart({ data, target }: { data: MeasureDataPoint[]; target: number }) {
  const maxVal = Math.max(...data.map((d) => d.value), target) + 5;
  const minVal = Math.min(...data.map((d) => d.value)) - 5;
  const range = maxVal - minVal;

  return (
    <div className="h-16 flex items-end gap-0.5 relative">
      {/* Target line */}
      <div
        className="absolute left-0 right-0 border-t border-dashed border-green-400"
        style={{ bottom: `${((target - minVal) / range) * 100}%` }}
      />
      {data.map((point, i) => {
        const height = ((point.value - minVal) / range) * 100;
        const isLast = i === data.length - 1;
        return (
          <div key={point.month} className="flex-1 flex flex-col items-center gap-0.5">
            <div
              className={`w-full rounded-t ${isLast ? "bg-primary" : "bg-primary/40"}`}
              style={{ height: `${height}%` }}
              title={`${point.month}: ${point.value}%`}
            />
            <span className="text-[9px] text-muted-foreground">{point.month}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function QualityMeasuresPage() {
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const filteredMeasures = categoryFilter === "all"
    ? mockMeasures
    : mockMeasures.filter((m) => m.category === categoryFilter);

  const avgRate = mockMeasures.reduce((s, m) => s + m.current_rate, 0) / mockMeasures.length;
  const atTarget = mockMeasures.filter((m) => m.current_rate >= m.target_rate).length;
  const improving = mockMeasures.filter((m) => m.trend === "up").length;

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Quality Measure Trends</h1>
          <p className="text-muted-foreground">
            Clinical quality measure performance and trends over time
          </p>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Measures Tracked</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mockMeasures.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Avg Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{avgRate.toFixed(1)}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">At Target</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {atTarget}/{mockMeasures.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Improving</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{improving}</div>
          </CardContent>
        </Card>
      </div>

      {/* Category Filter */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-sm font-medium text-muted-foreground">Category:</span>
        <Button
          variant={categoryFilter === "all" ? "default" : "outline"}
          size="sm"
          onClick={() => setCategoryFilter("all")}
          className="text-xs"
        >
          All
        </Button>
        {categories.map((cat) => (
          <Button
            key={cat}
            variant={categoryFilter === cat ? "default" : "outline"}
            size="sm"
            onClick={() => setCategoryFilter(cat)}
            className="text-xs"
          >
            {cat}
          </Button>
        ))}
      </div>

      {/* Measures Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredMeasures.map((measure) => {
          const gapToTarget = measure.target_rate - measure.current_rate;
          const atOrAboveTarget = gapToTarget <= 0;
          return (
            <Card key={measure.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-sm font-semibold">{measure.name}</CardTitle>
                    <CardDescription className="text-xs mt-0.5">
                      {measure.measure_id} — {measure.category}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-1">
                    {measure.trend === "up" ? (
                      <ArrowUpRight className="h-4 w-4 text-green-600" />
                    ) : measure.trend === "down" ? (
                      <ArrowDownRight className="h-4 w-4 text-red-600" />
                    ) : null}
                    <span className={`text-xs font-medium ${
                      measure.trend === "up" ? "text-green-600" :
                      measure.trend === "down" ? "text-red-600" : "text-muted-foreground"
                    }`}>
                      {measure.trend_pct > 0 ? "+" : ""}{measure.trend_pct}%
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {/* Rate and target */}
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-2xl font-bold">{measure.current_rate}%</span>
                    <span className="text-xs text-muted-foreground ml-2">
                      ({measure.numerator}/{measure.denominator})
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-1 text-xs">
                      <Target className="h-3 w-3" />
                      <span className={atOrAboveTarget ? "text-green-600 font-medium" : "text-muted-foreground"}>
                        Target: {measure.target_rate}%
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Benchmark: {measure.benchmark_rate}%
                    </div>
                  </div>
                </div>

                {/* Progress bar to target */}
                <div className="h-2 bg-muted rounded-full overflow-hidden mb-3 relative">
                  <div
                    className={`h-full rounded-full ${atOrAboveTarget ? "bg-green-500" : "bg-primary"}`}
                    style={{ width: `${Math.min((measure.current_rate / measure.target_rate) * 100, 100)}%` }}
                  />
                  {!atOrAboveTarget && (
                    <div className="absolute right-0 top-0 h-full w-px bg-green-500" title="Target" />
                  )}
                </div>

                {/* Trend chart */}
                <TrendChart data={measure.data} target={measure.target_rate} />

                {/* Gap info */}
                {!atOrAboveTarget && (
                  <div className="mt-2 text-xs text-amber-600">
                    {gapToTarget.toFixed(1)}% gap to target
                    ({Math.round(gapToTarget * measure.denominator / 100)} additional patients needed)
                  </div>
                )}
                {atOrAboveTarget && (
                  <div className="mt-2 text-xs text-green-600">
                    Exceeds target by {Math.abs(gapToTarget).toFixed(1)}%
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
