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
import { Progress } from "@/components/ui/progress";
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
import {
  ArrowLeft,
  Pill,
  TrendingUp,
  TrendingDown,
  Users,
  RefreshCw,
  Download,
  AlertTriangle,
  CheckCircle,
  Clock,
  DollarSign,
  BarChart3,
  Activity,
  Search,
  Filter,
} from "lucide-react";
import {
  Bar,
  BarChart,
  Line,
  LineChart,
  Pie,
  PieChart,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Area,
  AreaChart,
} from "recharts";

// Types
interface DrugUtilization {
  drugId: string;
  drugName: string;
  drugClass: string;
  rxNormCode: string;
  prescriptionCount: number;
  patientCount: number;
  totalDaysSupply: number;
  avgDaysSupply: number;
  avgDose: string;
  adherenceRate: number;
  discontinuationRate: number;
  switchRate: number;
  costPerPatient: number;
  formularyStatus: "preferred" | "non-preferred" | "specialty";
}

interface AdherenceMetric {
  drugClass: string;
  pdc80: number; // Proportion of Days Covered >= 80%
  mpr: number; // Medication Possession Ratio
  persistence: number; // % still on therapy at 1 year
  avgGapDays: number;
}

interface TrendData {
  month: string;
  prescriptions: number;
  patients: number;
  adherence: number;
}


// Mock Data
const mockDrugClasses = [
  { value: "all", label: "All Drug Classes" },
  { value: "antidiabetics", label: "Antidiabetics" },
  { value: "antihypertensives", label: "Antihypertensives" },
  { value: "statins", label: "Statins/Lipid-Lowering" },
  { value: "anticoagulants", label: "Anticoagulants" },
  { value: "ssris", label: "SSRIs/Antidepressants" },
  { value: "opioids", label: "Opioids" },
];

const mockDrugUtilization: DrugUtilization[] = [
  {
    drugId: "drug-001",
    drugName: "Metformin 500mg",
    drugClass: "Antidiabetics",
    rxNormCode: "861007",
    prescriptionCount: 4250,
    patientCount: 1820,
    totalDaysSupply: 127500,
    avgDaysSupply: 30,
    avgDose: "1000mg/day",
    adherenceRate: 72,
    discontinuationRate: 18,
    switchRate: 8,
    costPerPatient: 45,
    formularyStatus: "preferred",
  },
  {
    drugId: "drug-002",
    drugName: "Lisinopril 10mg",
    drugClass: "Antihypertensives",
    rxNormCode: "314076",
    prescriptionCount: 3890,
    patientCount: 1650,
    totalDaysSupply: 116700,
    avgDaysSupply: 30,
    avgDose: "10mg/day",
    adherenceRate: 68,
    discontinuationRate: 22,
    switchRate: 12,
    costPerPatient: 28,
    formularyStatus: "preferred",
  },
  {
    drugId: "drug-003",
    drugName: "Atorvastatin 20mg",
    drugClass: "Statins",
    rxNormCode: "617310",
    prescriptionCount: 3420,
    patientCount: 1480,
    totalDaysSupply: 102600,
    avgDaysSupply: 30,
    avgDose: "20mg/day",
    adherenceRate: 65,
    discontinuationRate: 28,
    switchRate: 5,
    costPerPatient: 52,
    formularyStatus: "preferred",
  },
  {
    drugId: "drug-004",
    drugName: "Ozempic 1mg",
    drugClass: "Antidiabetics",
    rxNormCode: "1991302",
    prescriptionCount: 1250,
    patientCount: 420,
    totalDaysSupply: 12600,
    avgDaysSupply: 30,
    avgDose: "1mg/week",
    adherenceRate: 82,
    discontinuationRate: 12,
    switchRate: 4,
    costPerPatient: 850,
    formularyStatus: "specialty",
  },
  {
    drugId: "drug-005",
    drugName: "Eliquis 5mg",
    drugClass: "Anticoagulants",
    rxNormCode: "1364430",
    prescriptionCount: 980,
    patientCount: 320,
    totalDaysSupply: 29400,
    avgDaysSupply: 30,
    avgDose: "5mg BID",
    adherenceRate: 78,
    discontinuationRate: 15,
    switchRate: 6,
    costPerPatient: 520,
    formularyStatus: "non-preferred",
  },
  {
    drugId: "drug-006",
    drugName: "Sertraline 50mg",
    drugClass: "SSRIs",
    rxNormCode: "312938",
    prescriptionCount: 2150,
    patientCount: 890,
    totalDaysSupply: 64500,
    avgDaysSupply: 30,
    avgDose: "50mg/day",
    adherenceRate: 58,
    discontinuationRate: 35,
    switchRate: 15,
    costPerPatient: 35,
    formularyStatus: "preferred",
  },
];

const mockAdherenceMetrics: AdherenceMetric[] = [
  { drugClass: "Antidiabetics", pdc80: 68, mpr: 0.72, persistence: 65, avgGapDays: 12 },
  { drugClass: "Antihypertensives", pdc80: 62, mpr: 0.68, persistence: 58, avgGapDays: 18 },
  { drugClass: "Statins", pdc80: 55, mpr: 0.62, persistence: 48, avgGapDays: 22 },
  { drugClass: "Anticoagulants", pdc80: 75, mpr: 0.78, persistence: 72, avgGapDays: 8 },
  { drugClass: "SSRIs", pdc80: 48, mpr: 0.55, persistence: 42, avgGapDays: 28 },
];

const mockTrendData: TrendData[] = [
  { month: "Jul", prescriptions: 12500, patients: 4800, adherence: 64 },
  { month: "Aug", prescriptions: 13200, patients: 5100, adherence: 65 },
  { month: "Sep", prescriptions: 13800, patients: 5350, adherence: 66 },
  { month: "Oct", prescriptions: 14200, patients: 5500, adherence: 67 },
  { month: "Nov", prescriptions: 14800, patients: 5720, adherence: 68 },
  { month: "Dec", prescriptions: 15100, patients: 5900, adherence: 68 },
  { month: "Jan", prescriptions: 15940, patients: 6580, adherence: 69 },
];

const mockDrugClassBreakdown = [
  { name: "Antidiabetics", value: 35, color: "#3b82f6" },
  { name: "Antihypertensives", value: 28, color: "#22c55e" },
  { name: "Statins", value: 18, color: "#f59e0b" },
  { name: "SSRIs", value: 12, color: "#8b5cf6" },
  { name: "Anticoagulants", value: 7, color: "#ec4899" },
];

const FORMULARY_COLORS = {
  preferred: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  "non-preferred": "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  specialty: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export default function DrugUtilizationPage() {
  const [drugClassFilter, setDrugClassFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [timeframe, setTimeframe] = useState("6m");
  const [isLoading, setIsLoading] = useState(false);

  // Filter drugs
  const filteredDrugs = useMemo(() => {
    return mockDrugUtilization.filter((drug) => {
      const matchesClass = drugClassFilter === "all" ||
        drug.drugClass.toLowerCase().includes(drugClassFilter);
      const matchesSearch = drug.drugName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        drug.rxNormCode.includes(searchQuery);
      return matchesClass && matchesSearch;
    });
  }, [drugClassFilter, searchQuery]);

  // Summary stats
  const summaryStats = useMemo(() => {
    const totalPrescriptions = mockDrugUtilization.reduce((sum, d) => sum + d.prescriptionCount, 0);
    const totalPatients = mockDrugUtilization.reduce((sum, d) => sum + d.patientCount, 0);
    const avgAdherence = mockDrugUtilization.reduce((sum, d) => sum + d.adherenceRate, 0) / mockDrugUtilization.length;
    const totalCost = mockDrugUtilization.reduce((sum, d) => sum + (d.costPerPatient * d.patientCount), 0);
    return { totalPrescriptions, totalPatients, avgAdherence, totalCost };
  }, []);

  const handleRefresh = async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setIsLoading(false);
  };

  const handleExport = () => {
    console.log("Exporting drug utilization data...");
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
              <Pill className="h-6 w-6 text-blue-600" />
              Drug Utilization Analytics
            </h1>
            <p className="text-muted-foreground">
              Prescribing patterns, adherence metrics, and formulary analysis
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={timeframe} onValueChange={setTimeframe}>
            <SelectTrigger className="w-32">
              <SelectValue placeholder="Timeframe" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="3m">3 Months</SelectItem>
              <SelectItem value="6m">6 Months</SelectItem>
              <SelectItem value="1y">1 Year</SelectItem>
              <SelectItem value="2y">2 Years</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-blue-100">
                <Pill className="h-4 w-4 text-blue-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {summaryStats.totalPrescriptions.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">Total Prescriptions</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-green-100">
                <Users className="h-4 w-4 text-green-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {summaryStats.totalPatients.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">Unique Patients</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-purple-100">
                <Activity className="h-4 w-4 text-purple-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-purple-600">
                  {summaryStats.avgAdherence.toFixed(1)}%
                </div>
                <p className="text-xs text-muted-foreground">Avg Adherence Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-amber-100">
                <DollarSign className="h-4 w-4 text-amber-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {formatCurrency(summaryStats.totalCost)}
                </div>
                <p className="text-xs text-muted-foreground">Total Drug Cost</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="utilization" className="space-y-4">
        <TabsList>
          <TabsTrigger value="utilization">Utilization</TabsTrigger>
          <TabsTrigger value="adherence">Adherence</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
          <TabsTrigger value="formulary">Formulary</TabsTrigger>
        </TabsList>

        {/* Utilization Tab */}
        <TabsContent value="utilization" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            {/* Drug Class Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle>Drug Class Distribution</CardTitle>
                <CardDescription>Prescription volume by class</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={mockDrugClassBreakdown}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={2}
                        dataKey="value"
                        label={({ value }) => `${value}%`}
                      >
                        {mockDrugClassBreakdown.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => `${value}%`} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Top Drugs Chart */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Top Prescribed Medications</CardTitle>
                <CardDescription>By prescription count</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={mockDrugUtilization.slice(0, 6)}
                      layout="vertical"
                      margin={{ left: 100 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis
                        type="category"
                        dataKey="drugName"
                        tick={{ fontSize: 11 }}
                        width={100}
                      />
                      <Tooltip />
                      <Bar dataKey="prescriptionCount" name="Prescriptions" fill="#3b82f6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Drug List */}
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle>Drug Utilization Details</CardTitle>
                  <CardDescription>Comprehensive medication metrics</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search drugs..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9 w-48"
                    />
                  </div>
                  <Select value={drugClassFilter} onValueChange={setDrugClassFilter}>
                    <SelectTrigger className="w-44">
                      <SelectValue placeholder="Drug Class" />
                    </SelectTrigger>
                    <SelectContent>
                      {mockDrugClasses.map((c) => (
                        <SelectItem key={c.value} value={c.value}>
                          {c.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Drug Name</TableHead>
                    <TableHead>Class</TableHead>
                    <TableHead className="text-right">Rx Count</TableHead>
                    <TableHead className="text-right">Patients</TableHead>
                    <TableHead className="text-right">Adherence</TableHead>
                    <TableHead className="text-right">Discont.</TableHead>
                    <TableHead className="text-right">Cost/Pt</TableHead>
                    <TableHead>Formulary</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDrugs.map((drug) => (
                    <TableRow key={drug.drugId}>
                      <TableCell>
                        <div>
                          <div className="font-medium">{drug.drugName}</div>
                          <div className="text-xs text-muted-foreground">
                            RxNorm: {drug.rxNormCode}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{drug.drugClass}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {drug.prescriptionCount.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        {drug.patientCount.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Progress value={drug.adherenceRate} className="w-16 h-2" />
                          <span className="text-sm w-10">{drug.adherenceRate}%</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge
                          variant="outline"
                          className={drug.discontinuationRate > 25 ? "border-red-500 text-red-600" : ""}
                        >
                          {drug.discontinuationRate}%
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(drug.costPerPatient)}
                      </TableCell>
                      <TableCell>
                        <Badge className={FORMULARY_COLORS[drug.formularyStatus]}>
                          {drug.formularyStatus}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Adherence Tab */}
        <TabsContent value="adherence" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Adherence Metrics by Drug Class</CardTitle>
              <CardDescription>
                PDC80, MPR, and persistence rates across therapeutic areas
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-80 mb-6">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={mockAdherenceMetrics}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="drugClass" tick={{ fontSize: 11 }} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="pdc80" name="PDC ≥ 80%" fill="#3b82f6" />
                    <Bar dataKey="persistence" name="1-Year Persistence" fill="#22c55e" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Drug Class</TableHead>
                    <TableHead className="text-right">PDC ≥ 80%</TableHead>
                    <TableHead className="text-right">MPR</TableHead>
                    <TableHead className="text-right">1-Year Persistence</TableHead>
                    <TableHead className="text-right">Avg Gap Days</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mockAdherenceMetrics.map((metric) => (
                    <TableRow key={metric.drugClass}>
                      <TableCell className="font-medium">{metric.drugClass}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Progress value={metric.pdc80} className="w-16 h-2" />
                          <span className="text-sm w-10">{metric.pdc80}%</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">{metric.mpr.toFixed(2)}</TableCell>
                      <TableCell className="text-right">{metric.persistence}%</TableCell>
                      <TableCell className="text-right">{metric.avgGapDays} days</TableCell>
                      <TableCell>
                        {metric.pdc80 >= 65 ? (
                          <Badge className="bg-green-100 text-green-800">
                            <CheckCircle className="h-3 w-3 mr-1" />
                            Good
                          </Badge>
                        ) : (
                          <Badge className="bg-amber-100 text-amber-800">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            Needs Improvement
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="mt-4 p-4 bg-muted rounded-lg text-sm text-muted-foreground">
                <p><strong>PDC ≥ 80%:</strong> Proportion of Days Covered at 80% or higher threshold</p>
                <p><strong>MPR:</strong> Medication Possession Ratio (days supply / days in period)</p>
                <p><strong>1-Year Persistence:</strong> % of patients still on therapy after 12 months</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trends Tab */}
        <TabsContent value="trends" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Prescription Volume Trend</CardTitle>
                <CardDescription>Monthly prescriptions and patient counts</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={mockTrendData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                      <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                      <Tooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="prescriptions"
                        name="Prescriptions"
                        stroke="#3b82f6"
                        fill="#3b82f6"
                        fillOpacity={0.3}
                      />
                      <Area
                        type="monotone"
                        dataKey="patients"
                        name="Patients"
                        stroke="#22c55e"
                        fill="#22c55e"
                        fillOpacity={0.3}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Adherence Trend</CardTitle>
                <CardDescription>Average adherence rate over time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={mockTrendData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                      <YAxis domain={[50, 80]} />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="adherence"
                        name="Adherence %"
                        stroke="#8b5cf6"
                        strokeWidth={2}
                        dot={true}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Formulary Tab */}
        <TabsContent value="formulary" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Formulary Compliance Analysis</CardTitle>
              <CardDescription>
                Prescribing patterns relative to formulary tiers
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 lg:grid-cols-3">
                <div className="text-center p-6 border rounded-lg">
                  <div className="text-4xl font-bold text-green-600">72%</div>
                  <p className="text-sm text-muted-foreground mt-2">Preferred Tier Usage</p>
                  <Progress value={72} className="mt-4" />
                </div>
                <div className="text-center p-6 border rounded-lg">
                  <div className="text-4xl font-bold text-amber-600">18%</div>
                  <p className="text-sm text-muted-foreground mt-2">Non-Preferred Usage</p>
                  <Progress value={18} className="mt-4" />
                </div>
                <div className="text-center p-6 border rounded-lg">
                  <div className="text-4xl font-bold text-purple-600">10%</div>
                  <p className="text-sm text-muted-foreground mt-2">Specialty Drug Usage</p>
                  <Progress value={10} className="mt-4" />
                </div>
              </div>

              <div className="mt-6">
                <h4 className="font-medium mb-4">Formulary Substitution Opportunities</h4>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Current Drug</TableHead>
                      <TableHead>Tier</TableHead>
                      <TableHead>Recommended Alternative</TableHead>
                      <TableHead>Savings/Pt</TableHead>
                      <TableHead>Patients</TableHead>
                      <TableHead className="text-right">Total Savings</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell className="font-medium">Eliquis 5mg</TableCell>
                      <TableCell>
                        <Badge className={FORMULARY_COLORS["non-preferred"]}>Non-Preferred</Badge>
                      </TableCell>
                      <TableCell>Warfarin (if appropriate)</TableCell>
                      <TableCell className="text-green-600">$480</TableCell>
                      <TableCell>85</TableCell>
                      <TableCell className="text-right font-medium text-green-600">
                        $40,800
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium">Ozempic 1mg</TableCell>
                      <TableCell>
                        <Badge className={FORMULARY_COLORS["specialty"]}>Specialty</Badge>
                      </TableCell>
                      <TableCell>Trulicity (preferred GLP-1)</TableCell>
                      <TableCell className="text-green-600">$250</TableCell>
                      <TableCell>120</TableCell>
                      <TableCell className="text-right font-medium text-green-600">
                        $30,000
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
