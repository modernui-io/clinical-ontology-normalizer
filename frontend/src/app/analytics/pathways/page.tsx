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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ArrowLeft,
  ArrowRight,
  Activity,
  Pill,
  RefreshCw,
  Download,
  Filter,
  Users,
  TrendingUp,
  Clock,
  ChevronRight,
  Target,
  Zap,
  BarChart3,
} from "lucide-react";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  Cell,
  Sankey,
  Rectangle,
  Layer,
} from "recharts";

// Types
interface PathwayStep {
  step: number;
  treatment: string;
  category: "drug" | "procedure" | "therapy";
  patientCount: number;
  percentage: number;
  avgDuration: number;
  outcomeSuccess: number;
}

interface TreatmentPathway {
  id: string;
  steps: PathwayStep[];
  totalPatients: number;
  avgDuration: number;
  successRate: number;
}

interface PathwayTransition {
  source: string;
  target: string;
  count: number;
  percentage: number;
}

interface SankeyNode {
  name: string;
}

interface SankeyLink {
  source: number;
  target: number;
  value: number;
}

// Mock Data
const mockConditions = [
  { value: "t2dm", label: "Type 2 Diabetes Mellitus" },
  { value: "hf", label: "Heart Failure" },
  { value: "copd", label: "COPD" },
  { value: "htn", label: "Hypertension" },
  { value: "ckd", label: "Chronic Kidney Disease" },
];

const mockPathways: TreatmentPathway[] = [
  {
    id: "path-001",
    totalPatients: 450,
    avgDuration: 365,
    successRate: 72,
    steps: [
      { step: 1, treatment: "Metformin", category: "drug", patientCount: 450, percentage: 100, avgDuration: 180, outcomeSuccess: 65 },
      { step: 2, treatment: "Metformin + Sulfonylurea", category: "drug", patientCount: 285, percentage: 63, avgDuration: 240, outcomeSuccess: 58 },
      { step: 3, treatment: "Add Insulin", category: "drug", patientCount: 125, percentage: 28, avgDuration: 365, outcomeSuccess: 72 },
    ],
  },
  {
    id: "path-002",
    totalPatients: 320,
    avgDuration: 420,
    successRate: 68,
    steps: [
      { step: 1, treatment: "Metformin", category: "drug", patientCount: 320, percentage: 100, avgDuration: 180, outcomeSuccess: 60 },
      { step: 2, treatment: "Metformin + GLP-1 RA", category: "drug", patientCount: 245, percentage: 77, avgDuration: 300, outcomeSuccess: 65 },
      { step: 3, treatment: "Add SGLT2i", category: "drug", patientCount: 98, percentage: 31, avgDuration: 420, outcomeSuccess: 68 },
    ],
  },
  {
    id: "path-003",
    totalPatients: 180,
    avgDuration: 280,
    successRate: 78,
    steps: [
      { step: 1, treatment: "Lifestyle + Metformin", category: "therapy", patientCount: 180, percentage: 100, avgDuration: 90, outcomeSuccess: 70 },
      { step: 2, treatment: "Add SGLT2i", category: "drug", patientCount: 156, percentage: 87, avgDuration: 180, outcomeSuccess: 75 },
      { step: 3, treatment: "Intensify GLP-1", category: "drug", patientCount: 72, percentage: 40, avgDuration: 280, outcomeSuccess: 78 },
    ],
  },
  {
    id: "path-004",
    totalPatients: 150,
    avgDuration: 200,
    successRate: 82,
    steps: [
      { step: 1, treatment: "Insulin", category: "drug", patientCount: 150, percentage: 100, avgDuration: 60, outcomeSuccess: 80 },
      { step: 2, treatment: "Basal-Bolus Regimen", category: "drug", patientCount: 120, percentage: 80, avgDuration: 180, outcomeSuccess: 82 },
    ],
  },
];

// Sankey data for treatment flow
const mockSankeyData = {
  nodes: [
    { name: "Diagnosis" },
    { name: "Metformin" },
    { name: "Lifestyle + Metformin" },
    { name: "Insulin" },
    { name: "Met + Sulfonylurea" },
    { name: "Met + GLP-1" },
    { name: "Met + SGLT2i" },
    { name: "Add Insulin" },
    { name: "Add SGLT2i" },
    { name: "Basal-Bolus" },
    { name: "Triple Therapy" },
    { name: "Controlled" },
    { name: "Uncontrolled" },
  ] as SankeyNode[],
  links: [
    { source: 0, target: 1, value: 770 },
    { source: 0, target: 2, value: 180 },
    { source: 0, target: 3, value: 150 },
    { source: 1, target: 4, value: 285 },
    { source: 1, target: 5, value: 245 },
    { source: 1, target: 6, value: 156 },
    { source: 2, target: 8, value: 156 },
    { source: 3, target: 9, value: 120 },
    { source: 4, target: 7, value: 125 },
    { source: 5, target: 8, value: 98 },
    { source: 6, target: 10, value: 72 },
    { source: 7, target: 11, value: 90 },
    { source: 7, target: 12, value: 35 },
    { source: 8, target: 11, value: 180 },
    { source: 8, target: 12, value: 74 },
    { source: 9, target: 11, value: 98 },
    { source: 9, target: 12, value: 22 },
    { source: 10, target: 11, value: 56 },
    { source: 10, target: 12, value: 16 },
  ] as SankeyLink[],
};

const mockTransitions: PathwayTransition[] = [
  { source: "Metformin", target: "Metformin + Sulfonylurea", count: 285, percentage: 37 },
  { source: "Metformin", target: "Metformin + GLP-1", count: 245, percentage: 32 },
  { source: "Metformin", target: "Metformin + SGLT2i", count: 156, percentage: 20 },
  { source: "Lifestyle + Metformin", target: "Add SGLT2i", count: 156, percentage: 87 },
  { source: "Insulin", target: "Basal-Bolus", count: 120, percentage: 80 },
  { source: "Metformin + Sulfonylurea", target: "Add Insulin", count: 125, percentage: 44 },
  { source: "Metformin + GLP-1", target: "Add SGLT2i", count: 98, percentage: 40 },
  { source: "Metformin + SGLT2i", target: "Triple Therapy", count: 72, percentage: 46 },
];

// Treatment category colors
const CATEGORY_COLORS = {
  drug: "#3b82f6",
  procedure: "#8b5cf6",
  therapy: "#22c55e",
};

const STEP_COLORS = [
  "#3b82f6",
  "#6366f1",
  "#8b5cf6",
  "#a855f7",
  "#d946ef",
];

// Custom Sankey node
const SankeyNodeComponent = (props: {
  x: number;
  y: number;
  width: number;
  height: number;
  index: number;
  payload: { name: string; value?: number };
}) => {
  const { x, y, width, height, payload } = props;
  const isStart = payload.name === "Diagnosis";
  const isEnd = payload.name === "Controlled" || payload.name === "Uncontrolled";

  return (
    <Layer key={`sankey-node-${props.index}`}>
      <Rectangle
        x={x}
        y={y}
        width={width}
        height={height}
        fill={isEnd ? (payload.name === "Controlled" ? "#22c55e" : "#ef4444") : "#6366f1"}
        fillOpacity={0.9}
      />
      <text
        textAnchor={isStart ? "start" : isEnd ? "end" : "middle"}
        x={isStart ? x + width + 6 : isEnd ? x - 6 : x + width / 2}
        y={y + height / 2}
        fontSize={11}
        fill="#374151"
        dominantBaseline="middle"
      >
        {payload.name}
      </text>
    </Layer>
  );
};

export default function TreatmentPathwaysPage() {
  const [selectedCondition, setSelectedCondition] = useState("t2dm");
  const [timeframe, setTimeframe] = useState("1y");
  const [isLoading, setIsLoading] = useState(false);

  const totalPatients = useMemo(() => {
    return mockPathways.reduce((sum, p) => sum + p.totalPatients, 0);
  }, []);

  const avgSuccessRate = useMemo(() => {
    const weighted = mockPathways.reduce(
      (sum, p) => sum + p.successRate * p.totalPatients,
      0
    );
    return (weighted / totalPatients).toFixed(1);
  }, [totalPatients]);

  const handleRefresh = async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setIsLoading(false);
  };

  const handleExport = () => {
    console.log("Exporting pathway data...");
  };

  // Prepare data for stacked bar chart showing pathway steps
  const stepChartData = useMemo(() => {
    const steps: Record<string, { step: number; [key: string]: number }> = {};

    mockPathways.forEach((pathway, pIdx) => {
      pathway.steps.forEach((step) => {
        if (!steps[`Step ${step.step}`]) {
          steps[`Step ${step.step}`] = { step: step.step };
        }
        steps[`Step ${step.step}`][`Pathway ${pIdx + 1}`] = step.patientCount;
      });
    });

    return Object.values(steps).sort((a, b) => a.step - b.step);
  }, []);

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
              <Activity className="h-6 w-6 text-purple-600" />
              Treatment Pathways
            </h1>
            <p className="text-muted-foreground">
              Analyze treatment sequences and patient flow through care pathways
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={selectedCondition} onValueChange={setSelectedCondition}>
            <SelectTrigger className="w-52">
              <SelectValue placeholder="Select condition" />
            </SelectTrigger>
            <SelectContent>
              {mockConditions.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={timeframe} onValueChange={setTimeframe}>
            <SelectTrigger className="w-32">
              <SelectValue placeholder="Timeframe" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="6m">6 Months</SelectItem>
              <SelectItem value="1y">1 Year</SelectItem>
              <SelectItem value="2y">2 Years</SelectItem>
              <SelectItem value="5y">5 Years</SelectItem>
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
                <Users className="h-4 w-4 text-blue-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">{totalPatients.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">Total Patients</p>
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
                <div className="text-2xl font-bold">{mockPathways.length}</div>
                <p className="text-xs text-muted-foreground">Distinct Pathways</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-green-100">
                <Target className="h-4 w-4 text-green-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-green-600">{avgSuccessRate}%</div>
                <p className="text-xs text-muted-foreground">Avg Success Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full bg-amber-100">
                <Clock className="h-4 w-4 text-amber-600" />
              </div>
              <div>
                <div className="text-2xl font-bold">312</div>
                <p className="text-xs text-muted-foreground">Avg Days to Control</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="flow" className="space-y-4">
        <TabsList>
          <TabsTrigger value="flow">Treatment Flow</TabsTrigger>
          <TabsTrigger value="pathways">Pathway Details</TabsTrigger>
          <TabsTrigger value="transitions">Transitions</TabsTrigger>
        </TabsList>

        {/* Treatment Flow (Sankey-like visualization) */}
        <TabsContent value="flow" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Treatment Flow Diagram</CardTitle>
              <CardDescription>
                Patient flow through treatment stages for {mockConditions.find(c => c.value === selectedCondition)?.label}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[500px]">
                <ResponsiveContainer width="100%" height="100%">
                  <Sankey
                    data={mockSankeyData}
                    node={<SankeyNodeComponent x={0} y={0} width={0} height={0} index={0} payload={{ name: '' }} />}
                    nodePadding={40}
                    margin={{ top: 20, right: 200, bottom: 20, left: 200 }}
                    link={{ stroke: "#d1d5db", strokeOpacity: 0.5 }}
                  >
                    <RechartsTooltip />
                  </Sankey>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 flex items-center justify-center gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-blue-500" />
                  <span>Diagnosis</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-indigo-500" />
                  <span>Treatment Steps</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-green-500" />
                  <span>Controlled</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-red-500" />
                  <span>Uncontrolled</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pathway Details */}
        <TabsContent value="pathways" className="space-y-4">
          <div className="grid gap-4">
            {mockPathways.map((pathway, pIdx) => (
              <Card key={pathway.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-lg">Pathway {pIdx + 1}</CardTitle>
                      <CardDescription>
                        {pathway.totalPatients.toLocaleString()} patients ({((pathway.totalPatients / totalPatients) * 100).toFixed(1)}%)
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-lg font-bold text-green-600">{pathway.successRate}%</div>
                        <p className="text-xs text-muted-foreground">Success Rate</p>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold">{pathway.avgDuration}</div>
                        <p className="text-xs text-muted-foreground">Avg Days</p>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2 overflow-x-auto pb-2">
                    {pathway.steps.map((step, sIdx) => (
                      <TooltipProvider key={sIdx}>
                        <div className="flex items-center">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div
                                className="flex flex-col items-center p-4 rounded-lg border-2 min-w-[160px] cursor-pointer hover:shadow-md transition-shadow"
                                style={{ borderColor: STEP_COLORS[sIdx % STEP_COLORS.length] }}
                              >
                                <div
                                  className="p-2 rounded-full mb-2"
                                  style={{ backgroundColor: `${STEP_COLORS[sIdx % STEP_COLORS.length]}20` }}
                                >
                                  <Pill
                                    className="h-5 w-5"
                                    style={{ color: STEP_COLORS[sIdx % STEP_COLORS.length] }}
                                  />
                                </div>
                                <span className="font-medium text-center text-sm">{step.treatment}</span>
                                <Badge variant="outline" className="mt-2">
                                  {step.patientCount.toLocaleString()} patients
                                </Badge>
                                <span className="text-xs text-muted-foreground mt-1">
                                  {step.outcomeSuccess}% success
                                </span>
                              </div>
                            </TooltipTrigger>
                            <TooltipContent>
                              <div className="text-sm">
                                <p><strong>Duration:</strong> {step.avgDuration} days avg</p>
                                <p><strong>Retention:</strong> {step.percentage}%</p>
                              </div>
                            </TooltipContent>
                          </Tooltip>
                          {sIdx < pathway.steps.length - 1 && (
                            <ChevronRight className="h-6 w-6 text-muted-foreground mx-2 flex-shrink-0" />
                          )}
                        </div>
                      </TooltipProvider>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Transitions */}
        <TabsContent value="transitions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Treatment Transitions</CardTitle>
              <CardDescription>
                Most common treatment changes and escalations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 lg:grid-cols-2">
                {/* Bar Chart */}
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={mockTransitions}
                      layout="vertical"
                      margin={{ left: 120 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis
                        type="category"
                        dataKey="source"
                        tick={{ fontSize: 11 }}
                        width={120}
                      />
                      <RechartsTooltip
                        formatter={(value) => [value, "Patients"]}
                      />
                      <Bar dataKey="count" fill="#6366f1" name="Patients">
                        {mockTransitions.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={STEP_COLORS[index % STEP_COLORS.length]}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Transitions Table */}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>From</TableHead>
                      <TableHead>To</TableHead>
                      <TableHead className="text-right">Patients</TableHead>
                      <TableHead className="text-right">%</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockTransitions.map((transition, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{transition.source}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <ArrowRight className="h-3 w-3 text-muted-foreground" />
                            {transition.target}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">{transition.count.toLocaleString()}</TableCell>
                        <TableCell className="text-right">
                          <Badge variant="outline">{transition.percentage}%</Badge>
                        </TableCell>
                      </TableRow>
                    ))}
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
