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
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  DollarSign,
  TrendingUp,
  TrendingDown,
  BarChart3,
  PieChart,
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Calendar,
  Filter,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart as RechartsPieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  LineChart,
  Line,
} from "recharts";

// Types
interface RevenueByCategory {
  category: string;
  potential: number;
  captured: number;
  gap: number;
  opportunities: number;
}

interface MonthlyTrend {
  month: string;
  potential: number;
  captured: number;
  recovered: number;
}

interface TopOpportunity {
  id: string;
  type: string;
  description: string;
  patientId: string;
  potentialRevenue: number;
  confidence: "high" | "medium" | "low";
  status: "new" | "in_progress" | "captured" | "missed";
  dueDate: string;
}

interface RevenueMetrics {
  totalPotential: number;
  totalCaptured: number;
  captureRate: number;
  monthOverMonth: number;
  yearOverYear: number;
  averagePerPatient: number;
  recoveredThisMonth: number;
  pendingOpportunities: number;
}

// Mock Data
const mockMetrics: RevenueMetrics = {
  totalPotential: 2850000,
  totalCaptured: 2137500,
  captureRate: 75,
  monthOverMonth: 8.5,
  yearOverYear: 12.3,
  averagePerPatient: 1250,
  recoveredThisMonth: 187500,
  pendingOpportunities: 342,
};

const mockRevenueByCategory: RevenueByCategory[] = [
  { category: "HCC Recapture", potential: 950000, captured: 712500, gap: 237500, opportunities: 156 },
  { category: "Coding Accuracy", potential: 620000, captured: 496000, gap: 124000, opportunities: 89 },
  { category: "CDI Queries", potential: 480000, captured: 336000, gap: 144000, opportunities: 42 },
  { category: "E/M Level", potential: 350000, captured: 280000, gap: 70000, opportunities: 28 },
  { category: "Procedure Capture", potential: 290000, captured: 203000, gap: 87000, opportunities: 19 },
  { category: "AWV/RAF", potential: 160000, captured: 110000, gap: 50000, opportunities: 8 },
];

const mockMonthlyTrends: MonthlyTrend[] = [
  { month: "Aug", potential: 215000, captured: 150000, recovered: 25000 },
  { month: "Sep", potential: 228000, captured: 165000, recovered: 32000 },
  { month: "Oct", potential: 235000, captured: 175000, recovered: 28000 },
  { month: "Nov", potential: 248000, captured: 185000, recovered: 35000 },
  { month: "Dec", potential: 262000, captured: 195000, recovered: 42000 },
  { month: "Jan", potential: 275000, captured: 206000, recovered: 45000 },
];

const mockTopOpportunities: TopOpportunity[] = [
  { id: "opp-001", type: "HCC Gap", description: "HCC 85 - Congestive Heart Failure", patientId: "P-1234", potentialRevenue: 8500, confidence: "high", status: "new", dueDate: "2026-02-15" },
  { id: "opp-002", type: "CDI Query", description: "Sepsis criteria documentation", patientId: "P-2345", potentialRevenue: 6200, confidence: "high", status: "in_progress", dueDate: "2026-01-30" },
  { id: "opp-003", type: "Coding", description: "E/M level upgrade opportunity", patientId: "P-3456", potentialRevenue: 4800, confidence: "medium", status: "new", dueDate: "2026-02-10" },
  { id: "opp-004", type: "HCC Gap", description: "HCC 18 - Diabetes with complications", patientId: "P-4567", potentialRevenue: 4500, confidence: "high", status: "new", dueDate: "2026-02-20" },
  { id: "opp-005", type: "Procedure", description: "Chronic care management codes", patientId: "P-5678", potentialRevenue: 3800, confidence: "medium", status: "in_progress", dueDate: "2026-02-05" },
  { id: "opp-006", type: "AWV", description: "Annual wellness visit RAF capture", patientId: "P-6789", potentialRevenue: 3200, confidence: "high", status: "new", dueDate: "2026-02-28" },
  { id: "opp-007", type: "CDI Query", description: "Malnutrition documentation", patientId: "P-7890", potentialRevenue: 2900, confidence: "medium", status: "new", dueDate: "2026-02-12" },
  { id: "opp-008", type: "Coding", description: "MCC/CC capture opportunity", patientId: "P-8901", potentialRevenue: 2600, confidence: "low", status: "in_progress", dueDate: "2026-01-28" },
];

const COLORS = {
  potential: "#3b82f6",
  captured: "#22c55e",
  gap: "#ef4444",
  recovered: "#8b5cf6",
};

const CATEGORY_COLORS = [
  "#3b82f6",
  "#22c55e",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
];

const confidenceColors: Record<string, string> = {
  high: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  low: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const statusColors: Record<string, string> = {
  new: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  in_progress: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  captured: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  missed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

export default function RevenueImpactPage() {
  const [timeframe, setTimeframe] = useState("6m");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(false);

  // Pie chart data for category breakdown
  const pieData = useMemo(() => {
    return mockRevenueByCategory.map((cat, idx) => ({
      name: cat.category,
      value: cat.potential,
      color: CATEGORY_COLORS[idx % CATEGORY_COLORS.length],
    }));
  }, []);

  // Capture rate by category for bar chart
  const captureRateData = useMemo(() => {
    return mockRevenueByCategory.map((cat) => ({
      category: cat.category.split(" ")[0], // Shorten labels
      captureRate: Math.round((cat.captured / cat.potential) * 100),
      gap: Math.round((cat.gap / cat.potential) * 100),
    }));
  }, []);

  const handleRefresh = async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setIsLoading(false);
  };

  const handleExport = () => {
    // Export logic would go here
    console.log("Exporting revenue data...");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/billing"
            className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <DollarSign className="h-6 w-6 text-green-600" />
              Revenue Impact Dashboard
            </h1>
            <p className="text-muted-foreground">
              Track revenue opportunities, capture rates, and financial performance
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={timeframe} onValueChange={setTimeframe}>
            <SelectTrigger className="w-32">
              <SelectValue placeholder="Timeframe" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1m">Last Month</SelectItem>
              <SelectItem value="3m">3 Months</SelectItem>
              <SelectItem value="6m">6 Months</SelectItem>
              <SelectItem value="1y">1 Year</SelectItem>
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

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Potential Revenue</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {formatCurrency(mockMetrics.totalPotential)}
            </div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
              <span>{mockMetrics.pendingOpportunities} open opportunities</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Captured Revenue</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(mockMetrics.totalCaptured)}
            </div>
            <div className="flex items-center gap-1 text-xs mt-1">
              <span className="text-green-600 flex items-center">
                <ArrowUpRight className="h-3 w-3" />
                {formatPercent(mockMetrics.monthOverMonth)} vs last month
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Capture Rate</CardTitle>
            <PieChart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mockMetrics.captureRate}%</div>
            <Progress value={mockMetrics.captureRate} className="mt-2" />
            <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
              <span>Target: 85%</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Recovered This Month</CardTitle>
            <CheckCircle className="h-4 w-4 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {formatCurrency(mockMetrics.recoveredThisMonth)}
            </div>
            <div className="flex items-center gap-1 text-xs text-green-600 mt-1">
              <ArrowUpRight className="h-3 w-3" />
              {formatPercent(mockMetrics.yearOverYear)} YoY
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Revenue Trend Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Revenue Trend</CardTitle>
            <CardDescription>Potential vs captured revenue over time</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockMonthlyTrends}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    formatter={(value) => formatCurrency(value as number)}
                    labelFormatter={(label) => `Month: ${label}`}
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="potential"
                    name="Potential"
                    stackId="1"
                    stroke={COLORS.potential}
                    fill={COLORS.potential}
                    fillOpacity={0.3}
                  />
                  <Area
                    type="monotone"
                    dataKey="captured"
                    name="Captured"
                    stackId="2"
                    stroke={COLORS.captured}
                    fill={COLORS.captured}
                    fillOpacity={0.6}
                  />
                  <Line
                    type="monotone"
                    dataKey="recovered"
                    name="Recovered"
                    stroke={COLORS.recovered}
                    strokeWidth={2}
                    dot={true}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Category Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Revenue by Category</CardTitle>
            <CardDescription>Potential revenue breakdown by opportunity type</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <RechartsPieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, percent }) =>
                      `${(name ?? "").split(" ")[0]} ${((percent ?? 0) * 100).toFixed(0)}%`
                    }
                    labelLine={true}
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => formatCurrency(value as number)} />
                </RechartsPieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Capture Rate by Category */}
      <Card>
        <CardHeader>
          <CardTitle>Capture Rate by Category</CardTitle>
          <CardDescription>
            Percentage of potential revenue captured in each category
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={captureRateData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="category" tick={{ fontSize: 12 }} width={80} />
                <Tooltip formatter={(value) => `${value}%`} />
                <Legend />
                <Bar dataKey="captureRate" name="Captured" stackId="a" fill={COLORS.captured} />
                <Bar dataKey="gap" name="Gap" stackId="a" fill={COLORS.gap} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Category Details Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Revenue by Category Details</CardTitle>
              <CardDescription>Detailed breakdown of revenue opportunities</CardDescription>
            </div>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Filter" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {mockRevenueByCategory.map((cat) => (
                  <SelectItem key={cat.category} value={cat.category}>
                    {cat.category}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Potential</TableHead>
                <TableHead className="text-right">Captured</TableHead>
                <TableHead className="text-right">Gap</TableHead>
                <TableHead className="text-right">Capture Rate</TableHead>
                <TableHead className="text-right">Opportunities</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockRevenueByCategory
                .filter((cat) => categoryFilter === "all" || cat.category === categoryFilter)
                .map((cat) => (
                  <TableRow key={cat.category}>
                    <TableCell className="font-medium">{cat.category}</TableCell>
                    <TableCell className="text-right">{formatCurrency(cat.potential)}</TableCell>
                    <TableCell className="text-right text-green-600">
                      {formatCurrency(cat.captured)}
                    </TableCell>
                    <TableCell className="text-right text-red-600">
                      {formatCurrency(cat.gap)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Progress
                          value={Math.round((cat.captured / cat.potential) * 100)}
                          className="w-16 h-2"
                        />
                        <span className="text-sm w-12">
                          {Math.round((cat.captured / cat.potential) * 100)}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant="outline">{cat.opportunities}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Top Opportunities */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Top Revenue Opportunities</CardTitle>
              <CardDescription>Highest impact opportunities to address</CardDescription>
            </div>
            <Link href="/billing">
              <Button variant="outline" size="sm">
                View All
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Patient</TableHead>
                <TableHead className="text-right">Potential</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Due Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockTopOpportunities.map((opp) => (
                <TableRow key={opp.id}>
                  <TableCell>
                    <Badge variant="outline">{opp.type}</Badge>
                  </TableCell>
                  <TableCell className="max-w-[200px] truncate">{opp.description}</TableCell>
                  <TableCell>
                    <Link
                      href={`/patients/${opp.patientId}`}
                      className="text-blue-600 hover:underline"
                    >
                      {opp.patientId}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right font-medium text-green-600">
                    {formatCurrency(opp.potentialRevenue)}
                  </TableCell>
                  <TableCell>
                    <Badge className={confidenceColors[opp.confidence]}>{opp.confidence}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className={statusColors[opp.status]}>
                      {opp.status.replace("_", " ")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(opp.dueDate).toLocaleDateString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
