"use client";

import { useState } from "react";
import { useROISummary } from "@/hooks/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  RefreshCw,
  Users,
  Target,
  TrendingUp,
  DollarSign,
  BarChart3,
  UserCheck,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from "recharts";

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(2)}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number): string {
  return value.toLocaleString();
}

export default function ROIDashboardPage() {
  const [conversionRate, setConversionRate] = useState(0.15);
  const [screeningCost, setScreeningCost] = useState(1.0);
  const [enrollmentValue, setEnrollmentValue] = useState(50_000);

  const { data, isLoading, refetch } = useROISummary({
    conversion_rate: conversionRate,
    screening_cost_per_patient: screeningCost,
    estimated_value_per_enrollment: enrollmentValue,
  });

  const overview = data?.screening_overview;
  const costAnalysis = data?.cost_analysis;
  const projected = data?.projected_enrollment;
  const eligibilityByTrial = data?.eligibility_by_trial ?? [];
  const siteBreakdown = data?.site_breakdown ?? [];
  const dualCandidates = data?.dual_enrollment_candidates ?? [];
  const timeSeries = data?.time_series ?? [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Screening ROI Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Screening volume, eligibility rates, and projected enrollment value
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Hero Stats Row */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Patients Screened
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : formatNumber(overview?.total_patients_screened ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              across {overview?.unique_trials_screened ?? 0} trials
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Eligible</CardTitle>
            <Target className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {isLoading ? "..." : formatNumber(overview?.total_eligible ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              of {formatNumber(overview?.total_screenings ?? 0)} screenings
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pass Rate</CardTitle>
            <BarChart3 className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {isLoading ? "..." : formatPercent(overview?.overall_pass_rate ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              overall eligibility rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Projected Enrollments
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {isLoading ? "..." : formatNumber(projected?.projected_enrollments ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              at {formatPercent(conversionRate)} conversion
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Cost / ROI Card + Parameter Controls */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-5 w-5" />
              Cost &amp; ROI Analysis
            </CardTitle>
            <CardDescription>
              Screening investment vs. projected enrollment value
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg border p-4">
                    <p className="text-sm text-muted-foreground">
                      Total Screening Cost
                    </p>
                    <p className="text-xl font-bold mt-1">
                      {formatCurrency(costAnalysis?.total_screening_cost ?? 0)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatNumber(costAnalysis?.patients_screened ?? 0)} patients
                      x {formatCurrency(costAnalysis?.screening_cost_per_patient ?? 0)}
                    </p>
                  </div>
                  <div className="rounded-lg border p-4">
                    <p className="text-sm text-muted-foreground">
                      Projected Enrollment Value
                    </p>
                    <p className="text-xl font-bold text-green-600 mt-1">
                      {formatCurrency(costAnalysis?.projected_enrollment_value ?? 0)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatNumber(costAnalysis?.projected_enrollments ?? 0)} enrollments
                      x {formatCurrency(costAnalysis?.estimated_value_per_enrollment ?? 0)}
                    </p>
                  </div>
                </div>
                <div className="rounded-lg bg-primary/5 border border-primary/20 p-4 text-center">
                  <p className="text-sm font-medium text-muted-foreground">
                    ROI Ratio
                  </p>
                  <p className="text-3xl font-bold text-primary mt-1">
                    {costAnalysis?.roi_ratio != null
                      ? `${costAnalysis.roi_ratio.toFixed(0)}x`
                      : "N/A"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    return on screening investment
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Model Parameters</CardTitle>
            <CardDescription>
              Adjust assumptions to see projected impact
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Conversion Rate</Label>
                <span className="text-sm font-mono font-medium">
                  {formatPercent(conversionRate)}
                </span>
              </div>
              <Slider
                value={[conversionRate * 100]}
                onValueChange={(v) => setConversionRate(v[0] / 100)}
                min={1}
                max={50}
                step={1}
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Screening Cost per Patient</Label>
                <span className="text-sm font-mono font-medium">
                  {formatCurrency(screeningCost)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">$</span>
                <Input
                  type="number"
                  min={0}
                  step={0.5}
                  value={screeningCost}
                  onChange={(e) =>
                    setScreeningCost(Math.max(0, parseFloat(e.target.value) || 0))
                  }
                  className="w-28"
                />
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Value per Enrollment</Label>
                <span className="text-sm font-mono font-medium">
                  {formatCurrency(enrollmentValue)}
                </span>
              </div>
              <Slider
                value={[enrollmentValue / 1000]}
                onValueChange={(v) => setEnrollmentValue(v[0] * 1000)}
                min={5}
                max={200}
                step={5}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Eligibility by Trial */}
      <Card>
        <CardHeader>
          <CardTitle>Eligibility by Trial</CardTitle>
          <CardDescription>Pass rates and screening counts per trial</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : eligibilityByTrial.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              No trial screening data yet
            </p>
          ) : (
            <div className="space-y-6">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={eligibilityByTrial.map((t) => ({
                      name: t.trial_name ?? t.trial_id,
                      Eligible: t.eligible_count,
                      Ineligible: t.ineligible_count,
                      Unknown: t.unknown_count,
                    }))}
                    margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="Eligible" fill="#22c55e" stackId="a" />
                    <Bar dataKey="Ineligible" fill="#ef4444" stackId="a" />
                    <Bar dataKey="Unknown" fill="#a3a3a3" stackId="a" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Trial</TableHead>
                      <TableHead className="text-right">Screened</TableHead>
                      <TableHead className="text-right">Eligible</TableHead>
                      <TableHead className="text-right">Ineligible</TableHead>
                      <TableHead className="text-right">Pass Rate</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {eligibilityByTrial.map((trial) => (
                      <TableRow key={trial.trial_id}>
                        <TableCell className="font-medium">
                          {trial.trial_name ?? trial.trial_id}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatNumber(trial.total_screened)}
                        </TableCell>
                        <TableCell className="text-right text-green-600 font-medium">
                          {formatNumber(trial.eligible_count)}
                        </TableCell>
                        <TableCell className="text-right text-red-600">
                          {formatNumber(trial.ineligible_count)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge
                            variant="outline"
                            className={
                              trial.pass_rate >= 0.5
                                ? "border-green-500 text-green-700"
                                : trial.pass_rate >= 0.25
                                  ? "border-yellow-500 text-yellow-700"
                                  : "border-red-500 text-red-700"
                            }
                          >
                            {formatPercent(trial.pass_rate)}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Site Breakdown + Dual Enrollment */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Site Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Site Breakdown</CardTitle>
            <CardDescription>
              Eligible patients per site per trial
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : siteBreakdown.length === 0 ? (
              <p className="py-8 text-center text-muted-foreground">
                No site data yet
              </p>
            ) : (
              <div className="rounded-lg border max-h-80 overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Site</TableHead>
                      <TableHead>Trial</TableHead>
                      <TableHead className="text-right">Eligible</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {siteBreakdown.map((row, i) => (
                      <TableRow key={`${row.site_id}-${row.trial_id}-${i}`}>
                        <TableCell className="font-medium">
                          {row.site_name ?? row.site_id}
                        </TableCell>
                        <TableCell>
                          {row.trial_name ?? row.trial_id}
                        </TableCell>
                        <TableCell className="text-right font-medium text-green-600">
                          {formatNumber(row.eligible_count)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Dual Enrollment Opportunities */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCheck className="h-5 w-5" />
              Dual Enrollment Opportunities
            </CardTitle>
            <CardDescription>
              Patients eligible for 2+ trials
              {data && (
                <Badge variant="secondary" className="ml-2">
                  {data.dual_enrollment_count} candidates
                </Badge>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : dualCandidates.length === 0 ? (
              <p className="py-8 text-center text-muted-foreground">
                No dual-enrollment candidates found
              </p>
            ) : (
              <div className="rounded-lg border max-h-80 overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Patient</TableHead>
                      <TableHead>Eligible Trials</TableHead>
                      <TableHead className="text-right">Count</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dualCandidates.map((c) => (
                      <TableRow key={c.patient_id}>
                        <TableCell className="font-mono text-sm">
                          {c.patient_id}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {c.eligible_trial_names.map((name, i) => (
                              <Badge
                                key={c.eligible_trial_ids[i]}
                                variant="outline"
                                className="text-xs"
                              >
                                {name}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {c.trial_count}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Time Series Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Screening Volume Over Time</CardTitle>
          <CardDescription>
            Daily screening volume and eligibility match rate
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : timeSeries.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              No time-series data yet
            </p>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={timeSeries.map((t) => ({
                    period: t.period,
                    Screenings: t.screenings,
                    Eligible: t.eligible,
                    "Match Rate": +(t.match_rate * 100).toFixed(1),
                  }))}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left" />
                  <YAxis yAxisId="right" orientation="right" unit="%" />
                  <Tooltip />
                  <Legend />
                  <Bar
                    yAxisId="left"
                    dataKey="Screenings"
                    fill="#6366f1"
                    opacity={0.3}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="Eligible"
                    stroke="#22c55e"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="Match Rate"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray="4 4"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
