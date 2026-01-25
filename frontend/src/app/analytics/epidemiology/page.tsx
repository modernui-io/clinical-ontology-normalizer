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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  Calculator,
  TrendingUp,
  TrendingDown,
  Users,
  Calendar,
  RefreshCw,
  Download,
  Filter,
  Info,
  Target,
  Clock,
  BarChart3,
  Activity,
  AlertTriangle,
} from "lucide-react";
import {
  Line,
  LineChart,
  Bar,
  BarChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Area,
  AreaChart,
  ReferenceLine,
} from "recharts";

// Types
interface EpidemiologyResult {
  condition: string;
  cohortSize: number;
  atRiskPopulation: number;
  incidenceCount: number;
  prevalenceCount: number;
  incidenceRate: number;
  prevalenceRate: number;
  personYears: number;
  confidenceIntervalLow: number;
  confidenceIntervalHigh: number;
}

interface TrendData {
  period: string;
  incidence: number;
  prevalence: number;
  population: number;
}

interface StratificationResult {
  stratum: string;
  incidence: number;
  prevalence: number;
  population: number;
  riskRatio: number;
}

// Mock Data
const mockConditions = [
  { value: "t2dm", label: "Type 2 Diabetes Mellitus", icd10: "E11" },
  { value: "hf", label: "Heart Failure", icd10: "I50" },
  { value: "copd", label: "COPD", icd10: "J44" },
  { value: "htn", label: "Hypertension", icd10: "I10" },
  { value: "ckd", label: "Chronic Kidney Disease", icd10: "N18" },
  { value: "asthma", label: "Asthma", icd10: "J45" },
  { value: "depression", label: "Major Depression", icd10: "F32" },
  { value: "obesity", label: "Obesity", icd10: "E66" },
];

const mockResult: EpidemiologyResult = {
  condition: "Type 2 Diabetes Mellitus",
  cohortSize: 125000,
  atRiskPopulation: 98500,
  incidenceCount: 4250,
  prevalenceCount: 18750,
  incidenceRate: 43.15,
  prevalenceRate: 15.0,
  personYears: 98500,
  confidenceIntervalLow: 41.8,
  confidenceIntervalHigh: 44.5,
};

const mockTrendData: TrendData[] = [
  { period: "2021 Q1", incidence: 38.2, prevalence: 12.1, population: 95000 },
  { period: "2021 Q2", incidence: 39.5, prevalence: 12.4, population: 96500 },
  { period: "2021 Q3", incidence: 40.1, prevalence: 12.8, population: 97200 },
  { period: "2021 Q4", incidence: 40.8, prevalence: 13.2, population: 98000 },
  { period: "2022 Q1", incidence: 41.2, prevalence: 13.5, population: 99500 },
  { period: "2022 Q2", incidence: 41.8, prevalence: 13.9, population: 101000 },
  { period: "2022 Q3", incidence: 42.1, prevalence: 14.2, population: 102500 },
  { period: "2022 Q4", incidence: 42.5, prevalence: 14.5, population: 104000 },
  { period: "2023 Q1", incidence: 42.8, prevalence: 14.7, population: 108000 },
  { period: "2023 Q2", incidence: 43.0, prevalence: 14.9, population: 112000 },
  { period: "2023 Q3", incidence: 43.1, prevalence: 15.0, population: 118000 },
  { period: "2023 Q4", incidence: 43.2, prevalence: 15.0, population: 125000 },
];

const mockAgeStratification: StratificationResult[] = [
  { stratum: "18-29", incidence: 8.5, prevalence: 2.1, population: 22000, riskRatio: 0.20 },
  { stratum: "30-39", incidence: 18.2, prevalence: 5.8, population: 28000, riskRatio: 0.42 },
  { stratum: "40-49", incidence: 35.6, prevalence: 12.4, population: 25000, riskRatio: 0.82 },
  { stratum: "50-59", incidence: 52.8, prevalence: 18.9, population: 22000, riskRatio: 1.22 },
  { stratum: "60-69", incidence: 68.4, prevalence: 24.5, population: 18000, riskRatio: 1.58 },
  { stratum: "70-79", incidence: 72.1, prevalence: 28.2, population: 7000, riskRatio: 1.67 },
  { stratum: "80+", incidence: 58.9, prevalence: 26.8, population: 3000, riskRatio: 1.36 },
];

const mockGenderStratification: StratificationResult[] = [
  { stratum: "Female", incidence: 40.2, prevalence: 14.1, population: 68000, riskRatio: 0.93 },
  { stratum: "Male", incidence: 46.8, prevalence: 16.2, population: 57000, riskRatio: 1.08 },
];

const mockRaceStratification: StratificationResult[] = [
  { stratum: "White", incidence: 41.5, prevalence: 14.5, population: 75000, riskRatio: 0.96 },
  { stratum: "Black", incidence: 52.3, prevalence: 18.8, population: 25000, riskRatio: 1.21 },
  { stratum: "Hispanic", incidence: 48.7, prevalence: 17.2, population: 18000, riskRatio: 1.13 },
  { stratum: "Asian", incidence: 35.2, prevalence: 11.8, population: 5000, riskRatio: 0.81 },
  { stratum: "Other", incidence: 43.1, prevalence: 15.0, population: 2000, riskRatio: 1.00 },
];

// Colors
const CHART_COLORS = {
  incidence: "#3b82f6",
  prevalence: "#22c55e",
  population: "#8b5cf6",
  riskRatio: "#f59e0b",
};

export default function EpidemiologyPage() {
  const [selectedCondition, setSelectedCondition] = useState("t2dm");
  const [startDate, setStartDate] = useState("2021-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [timeWindow, setTimeWindow] = useState("365");
  const [minObservation, setMinObservation] = useState("180");
  const [isLoading, setIsLoading] = useState(false);
  const [isCalculated, setIsCalculated] = useState(true);

  const handleCalculate = async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1500));
    setIsCalculated(true);
    setIsLoading(false);
  };

  const handleExport = () => {
    console.log("Exporting epidemiology data...");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/analytics"
            className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Calculator className="h-6 w-6 text-blue-600" />
              Incidence & Prevalence Calculator
            </h1>
            <p className="text-muted-foreground">
              Calculate and analyze disease incidence and prevalence rates
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Analysis Configuration
          </CardTitle>
          <CardDescription>
            Define cohort parameters for incidence and prevalence calculation
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <Label>Condition</Label>
              <Select value={selectedCondition} onValueChange={setSelectedCondition}>
                <SelectTrigger>
                  <SelectValue placeholder="Select condition" />
                </SelectTrigger>
                <SelectContent>
                  {mockConditions.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label} ({c.icd10})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Observation Period Start</Label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Observation Period End</Label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Time at Risk Window (days)</Label>
              <Select value={timeWindow} onValueChange={setTimeWindow}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="180">180 days</SelectItem>
                  <SelectItem value="365">365 days (1 year)</SelectItem>
                  <SelectItem value="730">730 days (2 years)</SelectItem>
                  <SelectItem value="1095">1095 days (3 years)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-4">
            <div className="space-y-2">
              <Label>Minimum Prior Observation (days)</Label>
              <Input
                type="number"
                value={minObservation}
                onChange={(e) => setMinObservation(e.target.value)}
                className="w-32"
              />
            </div>
            <div className="flex items-center space-x-2 mt-6">
              <Checkbox id="exclude-prior" defaultChecked />
              <Label htmlFor="exclude-prior" className="text-sm font-normal">
                Exclude prior diagnosis
              </Label>
            </div>
            <div className="flex items-center space-x-2 mt-6">
              <Checkbox id="first-occurrence" defaultChecked />
              <Label htmlFor="first-occurrence" className="text-sm font-normal">
                First occurrence only
              </Label>
            </div>
          </div>

          <div className="mt-6">
            <Button onClick={handleCalculate} disabled={isLoading}>
              {isLoading ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Calculating...
                </>
              ) : (
                <>
                  <Calculator className="mr-2 h-4 w-4" />
                  Calculate Rates
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {isCalculated && (
        <>
          {/* Results Summary */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-blue-100">
                    <TrendingUp className="h-4 w-4 text-blue-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-blue-600">
                      {mockResult.incidenceRate.toFixed(1)}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Incidence Rate (per 1,000 PY)
                    </p>
                    <p className="text-xs text-muted-foreground">
                      95% CI: [{mockResult.confidenceIntervalLow.toFixed(1)} - {mockResult.confidenceIntervalHigh.toFixed(1)}]
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-green-100">
                    <Activity className="h-4 w-4 text-green-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-green-600">
                      {mockResult.prevalenceRate.toFixed(1)}%
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Point Prevalence
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {mockResult.prevalenceCount.toLocaleString()} cases
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-purple-100">
                    <Users className="h-4 w-4 text-purple-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold">
                      {mockResult.cohortSize.toLocaleString()}
                    </div>
                    <p className="text-xs text-muted-foreground">Total Population</p>
                    <p className="text-xs text-muted-foreground">
                      {mockResult.atRiskPopulation.toLocaleString()} at risk
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-amber-100">
                    <Target className="h-4 w-4 text-amber-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold">
                      {mockResult.incidenceCount.toLocaleString()}
                    </div>
                    <p className="text-xs text-muted-foreground">New Cases</p>
                    <p className="text-xs text-muted-foreground">
                      {mockResult.personYears.toLocaleString()} person-years
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Tabs */}
          <Tabs defaultValue="trends" className="space-y-4">
            <TabsList>
              <TabsTrigger value="trends">Trends Over Time</TabsTrigger>
              <TabsTrigger value="stratification">Stratification</TabsTrigger>
              <TabsTrigger value="comparison">Condition Comparison</TabsTrigger>
            </TabsList>

            {/* Trends */}
            <TabsContent value="trends" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Incidence and Prevalence Trends</CardTitle>
                  <CardDescription>
                    Quarterly rates over the observation period
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={mockTrendData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                        <YAxis yAxisId="left" />
                        <YAxis yAxisId="right" orientation="right" />
                        <Tooltip />
                        <Legend />
                        <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="incidence"
                          name="Incidence (per 1,000 PY)"
                          stroke={CHART_COLORS.incidence}
                          strokeWidth={2}
                          dot={true}
                        />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="prevalence"
                          name="Prevalence (%)"
                          stroke={CHART_COLORS.prevalence}
                          strokeWidth={2}
                          dot={true}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Population Growth</CardTitle>
                  <CardDescription>
                    At-risk population over time
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={mockTrendData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                        <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                        <Tooltip formatter={(value) => [(value as number).toLocaleString(), "Population"]} />
                        <Area
                          type="monotone"
                          dataKey="population"
                          stroke={CHART_COLORS.population}
                          fill={CHART_COLORS.population}
                          fillOpacity={0.3}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Stratification */}
            <TabsContent value="stratification" className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                {/* Age Stratification */}
                <Card>
                  <CardHeader>
                    <CardTitle>By Age Group</CardTitle>
                    <CardDescription>Incidence and prevalence by age</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64 mb-4">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={mockAgeStratification}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="stratum" tick={{ fontSize: 11 }} />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Bar
                            dataKey="incidence"
                            name="Incidence"
                            fill={CHART_COLORS.incidence}
                          />
                          <Bar
                            dataKey="prevalence"
                            name="Prevalence"
                            fill={CHART_COLORS.prevalence}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Age</TableHead>
                          <TableHead className="text-right">Inc.</TableHead>
                          <TableHead className="text-right">Prev.</TableHead>
                          <TableHead className="text-right">Pop.</TableHead>
                          <TableHead className="text-right">RR</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {mockAgeStratification.map((row) => (
                          <TableRow key={row.stratum}>
                            <TableCell>{row.stratum}</TableCell>
                            <TableCell className="text-right">{row.incidence.toFixed(1)}</TableCell>
                            <TableCell className="text-right">{row.prevalence.toFixed(1)}%</TableCell>
                            <TableCell className="text-right">{row.population.toLocaleString()}</TableCell>
                            <TableCell className="text-right">
                              <Badge
                                variant="outline"
                                className={row.riskRatio > 1 ? "border-red-500 text-red-600" : ""}
                              >
                                {row.riskRatio.toFixed(2)}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>

                {/* Gender Stratification */}
                <Card>
                  <CardHeader>
                    <CardTitle>By Gender & Race/Ethnicity</CardTitle>
                    <CardDescription>Demographic disparities</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-6">
                      <div>
                        <h4 className="text-sm font-medium mb-3">Gender</h4>
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Gender</TableHead>
                              <TableHead className="text-right">Inc.</TableHead>
                              <TableHead className="text-right">Prev.</TableHead>
                              <TableHead className="text-right">RR</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {mockGenderStratification.map((row) => (
                              <TableRow key={row.stratum}>
                                <TableCell>{row.stratum}</TableCell>
                                <TableCell className="text-right">{row.incidence.toFixed(1)}</TableCell>
                                <TableCell className="text-right">{row.prevalence.toFixed(1)}%</TableCell>
                                <TableCell className="text-right">
                                  <Badge variant="outline">{row.riskRatio.toFixed(2)}</Badge>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>

                      <div>
                        <h4 className="text-sm font-medium mb-3">Race/Ethnicity</h4>
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Race</TableHead>
                              <TableHead className="text-right">Inc.</TableHead>
                              <TableHead className="text-right">Prev.</TableHead>
                              <TableHead className="text-right">RR</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {mockRaceStratification.map((row) => (
                              <TableRow key={row.stratum}>
                                <TableCell>{row.stratum}</TableCell>
                                <TableCell className="text-right">{row.incidence.toFixed(1)}</TableCell>
                                <TableCell className="text-right">{row.prevalence.toFixed(1)}%</TableCell>
                                <TableCell className="text-right">
                                  <Badge
                                    variant="outline"
                                    className={row.riskRatio > 1.1 ? "border-amber-500 text-amber-600" : ""}
                                  >
                                    {row.riskRatio.toFixed(2)}
                                  </Badge>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Comparison */}
            <TabsContent value="comparison" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Multi-Condition Comparison</CardTitle>
                  <CardDescription>
                    Compare incidence and prevalence across conditions
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Condition</TableHead>
                        <TableHead className="text-right">Incidence</TableHead>
                        <TableHead className="text-right">Prevalence</TableHead>
                        <TableHead className="text-right">Population</TableHead>
                        <TableHead className="text-right">Trend</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <TableRow>
                        <TableCell className="font-medium">Type 2 Diabetes</TableCell>
                        <TableCell className="text-right">43.2</TableCell>
                        <TableCell className="text-right">15.0%</TableCell>
                        <TableCell className="text-right">125,000</TableCell>
                        <TableCell className="text-right">
                          <Badge className="bg-amber-100 text-amber-800">
                            <TrendingUp className="h-3 w-3 mr-1" />
                            +2.1%
                          </Badge>
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="font-medium">Hypertension</TableCell>
                        <TableCell className="text-right">58.6</TableCell>
                        <TableCell className="text-right">28.4%</TableCell>
                        <TableCell className="text-right">125,000</TableCell>
                        <TableCell className="text-right">
                          <Badge className="bg-amber-100 text-amber-800">
                            <TrendingUp className="h-3 w-3 mr-1" />
                            +1.8%
                          </Badge>
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="font-medium">Heart Failure</TableCell>
                        <TableCell className="text-right">12.8</TableCell>
                        <TableCell className="text-right">4.2%</TableCell>
                        <TableCell className="text-right">125,000</TableCell>
                        <TableCell className="text-right">
                          <Badge className="bg-green-100 text-green-800">
                            <TrendingDown className="h-3 w-3 mr-1" />
                            -0.5%
                          </Badge>
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="font-medium">COPD</TableCell>
                        <TableCell className="text-right">8.4</TableCell>
                        <TableCell className="text-right">3.8%</TableCell>
                        <TableCell className="text-right">125,000</TableCell>
                        <TableCell className="text-right">
                          <Badge className="bg-green-100 text-green-800">
                            <TrendingDown className="h-3 w-3 mr-1" />
                            -1.2%
                          </Badge>
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="font-medium">CKD</TableCell>
                        <TableCell className="text-right">22.4</TableCell>
                        <TableCell className="text-right">8.6%</TableCell>
                        <TableCell className="text-right">125,000</TableCell>
                        <TableCell className="text-right">
                          <Badge className="bg-amber-100 text-amber-800">
                            <TrendingUp className="h-3 w-3 mr-1" />
                            +3.5%
                          </Badge>
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>

                  <div className="mt-4 p-4 bg-muted rounded-lg">
                    <div className="flex items-start gap-2">
                      <Info className="h-4 w-4 text-muted-foreground mt-0.5" />
                      <div className="text-sm text-muted-foreground">
                        <p>
                          <strong>Incidence rate</strong> is expressed per 1,000 person-years at risk.
                        </p>
                        <p>
                          <strong>Prevalence</strong> is point prevalence at the end of the observation period.
                        </p>
                        <p>
                          <strong>Trend</strong> represents year-over-year change in incidence rate.
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
