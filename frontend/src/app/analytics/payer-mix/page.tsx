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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  Users,
  DollarSign,
  TrendingUp,
  PieChart,
} from "lucide-react";

interface PayerData {
  id: string;
  name: string;
  type: "medicare_advantage" | "medicare_ffs" | "medicaid" | "commercial" | "self_pay" | "other";
  patient_count: number;
  total_revenue: number;
  avg_raf_score: number | null;
  avg_hcc_gaps: number;
  revenue_opportunity: number;
  pct_of_total: number;
  color: string;
  year_over_year_change: number;
}

interface PayerMetrics {
  total_patients: number;
  total_revenue: number;
  total_opportunity: number;
  avg_raf_all_ma: number;
  risk_adjusted_payers_pct: number;
}

const mockPayerData: PayerData[] = [
  {
    id: "1", name: "Medicare Advantage", type: "medicare_advantage",
    patient_count: 1245, total_revenue: 3_850_000, avg_raf_score: 1.42,
    avg_hcc_gaps: 2.3, revenue_opportunity: 445_000, pct_of_total: 35.2,
    color: "bg-blue-500", year_over_year_change: 8.5,
  },
  {
    id: "2", name: "Commercial (PPO/HMO)", type: "commercial",
    patient_count: 980, total_revenue: 2_940_000, avg_raf_score: null,
    avg_hcc_gaps: 0, revenue_opportunity: 125_000, pct_of_total: 27.7,
    color: "bg-green-500", year_over_year_change: 3.2,
  },
  {
    id: "3", name: "Medicare FFS", type: "medicare_ffs",
    patient_count: 620, total_revenue: 1_550_000, avg_raf_score: null,
    avg_hcc_gaps: 1.1, revenue_opportunity: 85_000, pct_of_total: 17.5,
    color: "bg-indigo-500", year_over_year_change: -2.1,
  },
  {
    id: "4", name: "Medicaid", type: "medicaid",
    patient_count: 410, total_revenue: 615_000, avg_raf_score: null,
    avg_hcc_gaps: 1.8, revenue_opportunity: 42_000, pct_of_total: 11.6,
    color: "bg-amber-500", year_over_year_change: 5.0,
  },
  {
    id: "5", name: "Self-Pay", type: "self_pay",
    patient_count: 180, total_revenue: 198_000, avg_raf_score: null,
    avg_hcc_gaps: 0, revenue_opportunity: 0, pct_of_total: 5.1,
    color: "bg-gray-500", year_over_year_change: -1.5,
  },
  {
    id: "6", name: "Other / Workers Comp", type: "other",
    patient_count: 105, total_revenue: 210_000, avg_raf_score: null,
    avg_hcc_gaps: 0, revenue_opportunity: 15_000, pct_of_total: 2.9,
    color: "bg-purple-500", year_over_year_change: 1.8,
  },
];

const mockMetrics: PayerMetrics = {
  total_patients: 3540,
  total_revenue: 9_363_000,
  total_opportunity: 712_000,
  avg_raf_all_ma: 1.42,
  risk_adjusted_payers_pct: 35.2,
};

const rafDistribution = [
  { range: "< 0.5", count: 85, pct: 6.8 },
  { range: "0.5 - 1.0", count: 312, pct: 25.1 },
  { range: "1.0 - 1.5", count: 425, pct: 34.1 },
  { range: "1.5 - 2.0", count: 268, pct: 21.5 },
  { range: "2.0 - 3.0", count: 112, pct: 9.0 },
  { range: "> 3.0", count: 43, pct: 3.5 },
];

export default function PayerMixPage() {
  const [sortBy, setSortBy] = useState<"patients" | "revenue" | "opportunity">("revenue");

  const sortedData = [...mockPayerData].sort((a, b) => {
    if (sortBy === "patients") return b.patient_count - a.patient_count;
    if (sortBy === "revenue") return b.total_revenue - a.total_revenue;
    return b.revenue_opportunity - a.revenue_opportunity;
  });

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Payer Mix Analysis</h1>
          <p className="text-muted-foreground">
            Revenue distribution, RAF scores, and coding opportunities by payer
          </p>
        </div>
      </div>

      {/* Top Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Patients</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mockMetrics.total_patients.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Revenue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${(mockMetrics.total_revenue / 1_000_000).toFixed(1)}M</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Revenue Gap</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">${(mockMetrics.total_opportunity / 1000).toFixed(0)}K</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Avg MA RAF</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">{mockMetrics.avg_raf_all_ma.toFixed(2)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Risk-Adjusted %</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mockMetrics.risk_adjusted_payers_pct}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Payer Distribution Bar */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <PieChart className="h-5 w-5" /> Payer Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-8 flex rounded-full overflow-hidden mb-4">
            {mockPayerData.map((payer) => (
              <div
                key={payer.id}
                className={`${payer.color} relative group`}
                style={{ width: `${payer.pct_of_total}%` }}
                title={`${payer.name}: ${payer.pct_of_total}%`}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-4">
            {mockPayerData.map((payer) => (
              <div key={payer.id} className="flex items-center gap-2 text-sm">
                <div className={`w-3 h-3 rounded-full ${payer.color}`} />
                <span>{payer.name} ({payer.pct_of_total}%)</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Payer Table */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Payer Breakdown</CardTitle>
                <div className="flex gap-1">
                  {(["revenue", "patients", "opportunity"] as const).map((s) => (
                    <Button
                      key={s}
                      variant={sortBy === s ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSortBy(s)}
                      className="text-xs"
                    >
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </Button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Payer</TableHead>
                    <TableHead className="text-right">Patients</TableHead>
                    <TableHead className="text-right">Revenue</TableHead>
                    <TableHead className="text-right">Avg RAF</TableHead>
                    <TableHead className="text-right">Opportunity</TableHead>
                    <TableHead className="text-right">YoY</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedData.map((payer) => (
                    <TableRow key={payer.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${payer.color}`} />
                          <span className="font-medium text-sm">{payer.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">{payer.patient_count.toLocaleString()}</TableCell>
                      <TableCell className="text-right">${(payer.total_revenue / 1000).toFixed(0)}K</TableCell>
                      <TableCell className="text-right">
                        {payer.avg_raf_score !== null ? payer.avg_raf_score.toFixed(2) : "—"}
                      </TableCell>
                      <TableCell className="text-right text-green-600">
                        {payer.revenue_opportunity > 0
                          ? `$${(payer.revenue_opportunity / 1000).toFixed(0)}K`
                          : "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={payer.year_over_year_change >= 0 ? "text-green-600" : "text-red-600"}>
                          {payer.year_over_year_change >= 0 ? "+" : ""}{payer.year_over_year_change}%
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        {/* RAF Distribution */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">MA RAF Distribution</CardTitle>
            <CardDescription>Medicare Advantage patients by RAF score range</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {rafDistribution.map((bucket) => (
                <div key={bucket.range} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium">{bucket.range}</span>
                    <span className="text-muted-foreground">{bucket.count} ({bucket.pct}%)</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-500 rounded-full"
                      style={{ width: `${(bucket.pct / 34.1) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
