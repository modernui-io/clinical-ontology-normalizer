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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ArrowLeft,
  Building2,
  DollarSign,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Download,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  FileText,
  Ban,
  Percent,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  LineChart,
  Line,
} from "recharts";

// Types
interface PayerMetrics {
  payerId: string;
  payerName: string;
  payerType: "Medicare" | "Medicaid" | "Commercial" | "Self-Pay" | "Workers Comp";
  claimsSubmitted: number;
  claimsPaid: number;
  claimsDenied: number;
  totalBilled: number;
  totalPaid: number;
  totalDenied: number;
  avgDaysToPayment: number;
  denialRate: number;
  collectionRate: number;
  writeOffAmount: number;
}

interface DenialReason {
  reason: string;
  count: number;
  amount: number;
  percentage: number;
  payerType: string;
}

interface MonthlyCollection {
  month: string;
  medicare: number;
  medicaid: number;
  commercial: number;
  selfPay: number;
}

interface PayerMixSummary {
  totalRevenue: number;
  medicarePercent: number;
  medicaidPercent: number;
  commercialPercent: number;
  selfPayPercent: number;
  avgDenialRate: number;
  avgCollectionRate: number;
  avgDaysToPayment: number;
  totalWriteOffs: number;
}

// Mock Data
const mockSummary: PayerMixSummary = {
  totalRevenue: 4850000,
  medicarePercent: 42,
  medicaidPercent: 18,
  commercialPercent: 32,
  selfPayPercent: 8,
  avgDenialRate: 8.5,
  avgCollectionRate: 87.2,
  avgDaysToPayment: 32,
  totalWriteOffs: 425000,
};

const mockPayerMetrics: PayerMetrics[] = [
  {
    payerId: "MCR-001",
    payerName: "Medicare Traditional",
    payerType: "Medicare",
    claimsSubmitted: 4250,
    claimsPaid: 3980,
    claimsDenied: 270,
    totalBilled: 1850000,
    totalPaid: 1520000,
    totalDenied: 162000,
    avgDaysToPayment: 21,
    denialRate: 6.4,
    collectionRate: 82.2,
    writeOffAmount: 168000,
  },
  {
    payerId: "MCR-002",
    payerName: "Medicare Advantage - Humana",
    payerType: "Medicare",
    claimsSubmitted: 1890,
    claimsPaid: 1720,
    claimsDenied: 170,
    totalBilled: 680000,
    totalPaid: 578000,
    totalDenied: 54400,
    avgDaysToPayment: 28,
    denialRate: 9.0,
    collectionRate: 85.0,
    writeOffAmount: 47600,
  },
  {
    payerId: "MCD-001",
    payerName: "State Medicaid",
    payerType: "Medicaid",
    claimsSubmitted: 2850,
    claimsPaid: 2450,
    claimsDenied: 400,
    totalBilled: 720000,
    totalPaid: 540000,
    totalDenied: 86400,
    avgDaysToPayment: 45,
    denialRate: 14.0,
    collectionRate: 75.0,
    writeOffAmount: 93600,
  },
  {
    payerId: "COM-001",
    payerName: "Blue Cross Blue Shield",
    payerType: "Commercial",
    claimsSubmitted: 3200,
    claimsPaid: 3040,
    claimsDenied: 160,
    totalBilled: 1150000,
    totalPaid: 1035000,
    totalDenied: 57500,
    avgDaysToPayment: 35,
    denialRate: 5.0,
    collectionRate: 90.0,
    writeOffAmount: 57500,
  },
  {
    payerId: "COM-002",
    payerName: "Aetna",
    payerType: "Commercial",
    claimsSubmitted: 1650,
    claimsPaid: 1551,
    claimsDenied: 99,
    totalBilled: 520000,
    totalPaid: 468000,
    totalDenied: 26000,
    avgDaysToPayment: 30,
    denialRate: 6.0,
    collectionRate: 90.0,
    writeOffAmount: 26000,
  },
  {
    payerId: "SELF-001",
    payerName: "Self-Pay",
    payerType: "Self-Pay",
    claimsSubmitted: 890,
    claimsPaid: 445,
    claimsDenied: 0,
    totalBilled: 280000,
    totalPaid: 112000,
    totalDenied: 0,
    avgDaysToPayment: 60,
    denialRate: 0,
    collectionRate: 40.0,
    writeOffAmount: 168000,
  },
];

const mockDenialReasons: DenialReason[] = [
  { reason: "Missing/Invalid Authorization", count: 245, amount: 98000, percentage: 22, payerType: "All" },
  { reason: "Patient Not Eligible", count: 189, amount: 75600, percentage: 17, payerType: "Commercial" },
  { reason: "Duplicate Claim", count: 156, amount: 46800, percentage: 14, payerType: "Medicare" },
  { reason: "Timely Filing Exceeded", count: 134, amount: 53600, percentage: 12, payerType: "Medicaid" },
  { reason: "Medical Necessity", count: 112, amount: 67200, percentage: 10, payerType: "Commercial" },
  { reason: "Incorrect Coding", count: 98, amount: 39200, percentage: 9, payerType: "All" },
  { reason: "Coordination of Benefits", count: 89, amount: 35600, percentage: 8, payerType: "Medicare" },
  { reason: "Other/Miscellaneous", count: 88, amount: 35200, percentage: 8, payerType: "All" },
];

const mockMonthlyCollections: MonthlyCollection[] = [
  { month: "Aug", medicare: 320000, medicaid: 135000, commercial: 245000, selfPay: 28000 },
  { month: "Sep", medicare: 345000, medicaid: 142000, commercial: 258000, selfPay: 32000 },
  { month: "Oct", medicare: 362000, medicaid: 148000, commercial: 272000, selfPay: 35000 },
  { month: "Nov", medicare: 378000, medicaid: 155000, commercial: 285000, selfPay: 38000 },
  { month: "Dec", medicare: 395000, medicaid: 162000, commercial: 298000, selfPay: 42000 },
  { month: "Jan", medicare: 410000, medicaid: 170000, commercial: 312000, selfPay: 45000 },
];

const PAYER_COLORS = {
  Medicare: "#3b82f6",
  Medicaid: "#22c55e",
  Commercial: "#8b5cf6",
  "Self-Pay": "#f59e0b",
  "Workers Comp": "#ec4899",
};

const payerTypeColors: Record<string, string> = {
  Medicare: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  Medicaid: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  Commercial: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  "Self-Pay": "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  "Workers Comp": "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export default function PayerMixAnalysisPage() {
  const [timeframe, setTimeframe] = useState("6m");
  const [payerFilter, setPayerFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(false);

  // Payer mix pie data
  const payerMixData = useMemo(() => [
    { name: "Medicare", value: mockSummary.medicarePercent, color: PAYER_COLORS.Medicare },
    { name: "Medicaid", value: mockSummary.medicaidPercent, color: PAYER_COLORS.Medicaid },
    { name: "Commercial", value: mockSummary.commercialPercent, color: PAYER_COLORS.Commercial },
    { name: "Self-Pay", value: mockSummary.selfPayPercent, color: PAYER_COLORS["Self-Pay"] },
  ], []);

  // Collection trend chart data
  const collectionTrendData = useMemo(() => {
    return mockMonthlyCollections.map((m) => ({
      ...m,
      total: m.medicare + m.medicaid + m.commercial + m.selfPay,
    }));
  }, []);

  // Filtered payer metrics
  const filteredPayerMetrics = useMemo(() => {
    if (payerFilter === "all") return mockPayerMetrics;
    return mockPayerMetrics.filter((p) => p.payerType === payerFilter);
  }, [payerFilter]);

  const handleRefresh = async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setIsLoading(false);
  };

  const handleExport = () => {
    console.log("Exporting payer mix data...");
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
              <Building2 className="h-6 w-6 text-purple-600" />
              Payer Mix Analysis
            </h1>
            <p className="text-muted-foreground">
              Revenue distribution by payer, denial rates, and collection trends
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

      {/* Summary KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(mockSummary.totalRevenue)}</div>
            <p className="text-xs text-muted-foreground">Across all payers</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg Collection Rate</CardTitle>
            <Percent className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{mockSummary.avgCollectionRate}%</div>
            <Progress value={mockSummary.avgCollectionRate} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg Denial Rate</CardTitle>
            <Ban className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{mockSummary.avgDenialRate}%</div>
            <p className="text-xs text-muted-foreground">Industry avg: 10%</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg Days to Payment</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mockSummary.avgDaysToPayment}</div>
            <p className="text-xs text-muted-foreground">days</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Payer Mix Pie Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Payer Mix Distribution</CardTitle>
            <CardDescription>Revenue breakdown by payer type</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={payerMixData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name} ${value}%`}
                    labelLine={true}
                  >
                    {payerMixData.map((entry, index) => (
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

        {/* Collection Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Collection Trend by Payer</CardTitle>
            <CardDescription>Monthly collections over time</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={collectionTrendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip formatter={(value) => formatCurrency(value as number)} />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="medicare"
                    name="Medicare"
                    stackId="1"
                    stroke={PAYER_COLORS.Medicare}
                    fill={PAYER_COLORS.Medicare}
                    fillOpacity={0.8}
                  />
                  <Area
                    type="monotone"
                    dataKey="medicaid"
                    name="Medicaid"
                    stackId="1"
                    stroke={PAYER_COLORS.Medicaid}
                    fill={PAYER_COLORS.Medicaid}
                    fillOpacity={0.8}
                  />
                  <Area
                    type="monotone"
                    dataKey="commercial"
                    name="Commercial"
                    stackId="1"
                    stroke={PAYER_COLORS.Commercial}
                    fill={PAYER_COLORS.Commercial}
                    fillOpacity={0.8}
                  />
                  <Area
                    type="monotone"
                    dataKey="selfPay"
                    name="Self-Pay"
                    stackId="1"
                    stroke={PAYER_COLORS["Self-Pay"]}
                    fill={PAYER_COLORS["Self-Pay"]}
                    fillOpacity={0.8}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs for Payer Details and Denial Analysis */}
      <Tabs defaultValue="payers" className="space-y-4">
        <TabsList>
          <TabsTrigger value="payers">Payer Performance</TabsTrigger>
          <TabsTrigger value="denials">Denial Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="payers">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Payer Performance Details</CardTitle>
                  <CardDescription>Key metrics by payer</CardDescription>
                </div>
                <Select value={payerFilter} onValueChange={setPayerFilter}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Filter" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Payers</SelectItem>
                    <SelectItem value="Medicare">Medicare</SelectItem>
                    <SelectItem value="Medicaid">Medicaid</SelectItem>
                    <SelectItem value="Commercial">Commercial</SelectItem>
                    <SelectItem value="Self-Pay">Self-Pay</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Payer</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Claims</TableHead>
                    <TableHead className="text-right">Billed</TableHead>
                    <TableHead className="text-right">Collected</TableHead>
                    <TableHead className="text-right">Collection %</TableHead>
                    <TableHead className="text-right">Denial %</TableHead>
                    <TableHead className="text-right">Days to Pay</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPayerMetrics.map((payer) => (
                    <TableRow key={payer.payerId}>
                      <TableCell className="font-medium">{payer.payerName}</TableCell>
                      <TableCell>
                        <Badge className={payerTypeColors[payer.payerType]}>{payer.payerType}</Badge>
                      </TableCell>
                      <TableCell className="text-right">{payer.claimsSubmitted.toLocaleString()}</TableCell>
                      <TableCell className="text-right">{formatCurrency(payer.totalBilled)}</TableCell>
                      <TableCell className="text-right text-green-600">
                        {formatCurrency(payer.totalPaid)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Progress value={payer.collectionRate} className="w-16 h-2" />
                          <span className="text-sm w-12">{payer.collectionRate}%</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge
                          variant="outline"
                          className={payer.denialRate > 10 ? "border-red-500 text-red-600" : ""}
                        >
                          {payer.denialRate}%
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">{payer.avgDaysToPayment}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="denials">
          <Card>
            <CardHeader>
              <CardTitle>Top Denial Reasons</CardTitle>
              <CardDescription>Most common reasons for claim denials</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 lg:grid-cols-2">
                {/* Denial Reasons Bar Chart */}
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={mockDenialReasons} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" tickFormatter={(v) => `${v}%`} />
                      <YAxis
                        type="category"
                        dataKey="reason"
                        tick={{ fontSize: 11 }}
                        width={150}
                        tickFormatter={(v) => v.length > 20 ? v.slice(0, 20) + "..." : v}
                      />
                      <Tooltip
                        formatter={(value, name) => [
                          name === "percentage" ? `${value}%` : formatCurrency(value as number),
                          name,
                        ]}
                      />
                      <Bar dataKey="percentage" name="% of Denials" fill="#ef4444" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Denial Reasons Table */}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Reason</TableHead>
                      <TableHead className="text-right">Count</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead className="text-right">% of Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockDenialReasons.map((denial, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="max-w-[200px] truncate font-medium">
                          {denial.reason}
                        </TableCell>
                        <TableCell className="text-right">{denial.count}</TableCell>
                        <TableCell className="text-right text-red-600">
                          {formatCurrency(denial.amount)}
                        </TableCell>
                        <TableCell className="text-right">{denial.percentage}%</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Write-offs Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Write-off Summary</CardTitle>
              <CardDescription>Total write-offs: {formatCurrency(mockSummary.totalWriteOffs)}</CardDescription>
            </div>
            <Badge variant="outline" className="text-lg">
              {((mockSummary.totalWriteOffs / mockSummary.totalRevenue) * 100).toFixed(1)}% of revenue
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
            {mockPayerMetrics.map((payer) => (
              <div key={payer.payerId} className="space-y-2">
                <div className="text-sm font-medium">{payer.payerName.split(" - ")[0]}</div>
                <div className="text-lg font-bold text-amber-600">
                  {formatCurrency(payer.writeOffAmount)}
                </div>
                <Progress
                  value={(payer.writeOffAmount / mockSummary.totalWriteOffs) * 100}
                  className="h-2"
                />
                <div className="text-xs text-muted-foreground">
                  {((payer.writeOffAmount / mockSummary.totalWriteOffs) * 100).toFixed(1)}% of total
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
