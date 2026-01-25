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
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
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
  Search,
  TrendingUp,
  TrendingDown,
  Minus,
  Filter,
  Info,
  BarChart2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  ZAxis,
} from "recharts";

// ============================================================================
// Types
// ============================================================================

interface DifferentialResult {
  id: string;
  name: string;
  description?: string;
  category: string;
  log2FoldChange: number;
  pValue: number;
  adjustedPValue: number;
  baseMean: number;
  significance: "upregulated" | "downregulated" | "not_significant";
}

interface VolcanoSettings {
  pValueThreshold: number;
  log2FCThreshold: number;
  showLabels: boolean;
  highlightTop: number;
}

// ============================================================================
// Mock Data
// ============================================================================

const generateMockData = (): DifferentialResult[] => {
  const categories = ["Clinical Marker", "Medication", "Comorbidity", "Lab Value", "Vital Sign"];
  const names = [
    "HbA1c Level", "BNP", "Troponin I", "CRP", "eGFR", "Albumin", "Hemoglobin",
    "Creatinine", "Sodium", "Potassium", "WBC Count", "Platelet Count",
    "Systolic BP", "Diastolic BP", "Heart Rate", "Temperature", "SpO2",
    "Metformin", "Lisinopril", "Aspirin", "Statin", "Beta Blocker",
    "Diabetes Type 2", "Hypertension", "CHF", "COPD", "CKD", "Anemia",
    "Prior MI", "Prior Stroke", "Atrial Fibrillation", "Depression",
    "Obesity", "Smoking Status", "Alcohol Use", "Fall Risk",
    "Frailty Score", "Barthel Index", "MMSE Score", "Pain Score"
  ];

  return names.map((name, i) => {
    const log2FC = (Math.random() - 0.5) * 6;
    const pValue = Math.pow(10, -(Math.random() * 6));
    const adjustedPValue = Math.min(1, pValue * 40);

    let significance: "upregulated" | "downregulated" | "not_significant" = "not_significant";
    if (adjustedPValue < 0.05 && log2FC > 1) significance = "upregulated";
    else if (adjustedPValue < 0.05 && log2FC < -1) significance = "downregulated";

    return {
      id: `var-${i}`,
      name,
      category: categories[i % categories.length],
      log2FoldChange: log2FC,
      pValue,
      adjustedPValue,
      baseMean: Math.random() * 1000 + 100,
      significance,
    };
  });
};

const mockData = generateMockData();

// ============================================================================
// Helper Functions
// ============================================================================

const getPointColor = (result: DifferentialResult, settings: VolcanoSettings) => {
  const { pValueThreshold, log2FCThreshold } = settings;
  const negLogP = -Math.log10(result.adjustedPValue);

  if (negLogP >= -Math.log10(pValueThreshold) && result.log2FoldChange >= log2FCThreshold) {
    return "#ef4444"; // red - upregulated
  }
  if (negLogP >= -Math.log10(pValueThreshold) && result.log2FoldChange <= -log2FCThreshold) {
    return "#3b82f6"; // blue - downregulated
  }
  return "#9ca3af"; // gray - not significant
};

const formatPValue = (pValue: number) => {
  if (pValue < 0.0001) return pValue.toExponential(2);
  if (pValue < 0.01) return pValue.toFixed(4);
  return pValue.toFixed(3);
};

// ============================================================================
// Custom Tooltip Component
// ============================================================================

interface TooltipPayload {
  name: string;
  log2FoldChange: number;
  adjustedPValue: number;
  category: string;
  baseMean: number;
  significance: string;
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: TooltipPayload }> }) => {
  if (active && payload && payload.length > 0) {
    const data = payload[0].payload;
    return (
      <div className="bg-popover border rounded-lg shadow-lg p-3 text-sm">
        <div className="font-medium">{data.name}</div>
        <div className="text-muted-foreground">{data.category}</div>
        <div className="mt-2 space-y-1">
          <div>Log2 FC: <span className="font-mono">{data.log2FoldChange.toFixed(3)}</span></div>
          <div>Adj. p-value: <span className="font-mono">{formatPValue(data.adjustedPValue)}</span></div>
          <div>Base Mean: <span className="font-mono">{data.baseMean.toFixed(1)}</span></div>
        </div>
        <Badge className="mt-2" variant={
          data.significance === "upregulated" ? "destructive" :
          data.significance === "downregulated" ? "default" : "secondary"
        }>
          {data.significance.replace("_", " ")}
        </Badge>
      </div>
    );
  }
  return null;
};

// ============================================================================
// Main Component
// ============================================================================

export default function VolcanoPlotPage() {
  const [data] = useState<DifferentialResult[]>(mockData);
  const [activeTab, setActiveTab] = useState("plot");
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [settings, setSettings] = useState<VolcanoSettings>({
    pValueThreshold: 0.05,
    log2FCThreshold: 1,
    showLabels: true,
    highlightTop: 10,
  });

  // Get unique categories
  const categories = useMemo(() => {
    const unique = new Set(data.map(d => d.category));
    return ["all", ...Array.from(unique)];
  }, [data]);

  // Transform data for scatter plot
  const plotData = useMemo(() => {
    return data
      .filter(d => categoryFilter === "all" || d.category === categoryFilter)
      .filter(d => searchQuery === "" || d.name.toLowerCase().includes(searchQuery.toLowerCase()))
      .map(d => ({
        ...d,
        x: d.log2FoldChange,
        y: -Math.log10(d.adjustedPValue),
      }));
  }, [data, categoryFilter, searchQuery]);

  // Get significant results
  const significantResults = useMemo(() => {
    return plotData
      .filter(d => d.significance !== "not_significant")
      .sort((a, b) => a.adjustedPValue - b.adjustedPValue);
  }, [plotData]);

  const upregulated = significantResults.filter(d => d.significance === "upregulated");
  const downregulated = significantResults.filter(d => d.significance === "downregulated");

  // Top results for labeling
  const topResults = useMemo(() => {
    return [...significantResults]
      .sort((a, b) => Math.abs(b.log2FoldChange) - Math.abs(a.log2FoldChange))
      .slice(0, settings.highlightTop);
  }, [significantResults, settings.highlightTop]);

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
            <h1 className="text-2xl font-bold tracking-tight">Volcano Plot</h1>
            <p className="text-muted-foreground">
              Differential analysis visualization for clinical variables
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

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Variables</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Significant</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{significantResults.length}</div>
            <div className="text-xs text-muted-foreground">
              p &lt; {settings.pValueThreshold}, |FC| &gt; {settings.log2FCThreshold}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-red-500" />
              Upregulated
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{upregulated.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-blue-500" />
              Downregulated
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{downregulated.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Not Significant</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-500">
              {data.length - significantResults.length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Settings Panel */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-center gap-8">
            <div className="flex items-center gap-4">
              <Label>P-value threshold:</Label>
              <Select
                value={String(settings.pValueThreshold)}
                onValueChange={(v) => setSettings({ ...settings, pValueThreshold: parseFloat(v) })}
              >
                <SelectTrigger className="w-[100px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0.01">0.01</SelectItem>
                  <SelectItem value="0.05">0.05</SelectItem>
                  <SelectItem value="0.1">0.1</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-4">
              <Label>Log2 FC threshold:</Label>
              <Select
                value={String(settings.log2FCThreshold)}
                onValueChange={(v) => setSettings({ ...settings, log2FCThreshold: parseFloat(v) })}
              >
                <SelectTrigger className="w-[100px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0.5">0.5</SelectItem>
                  <SelectItem value="1">1.0</SelectItem>
                  <SelectItem value="1.5">1.5</SelectItem>
                  <SelectItem value="2">2.0</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={settings.showLabels}
                onCheckedChange={(c) => setSettings({ ...settings, showLabels: c })}
              />
              <Label>Show Labels</Label>
            </div>
            <div className="flex items-center gap-4">
              <Label>Category:</Label>
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {categories.map(c => (
                    <SelectItem key={c} value={c}>
                      {c === "all" ? "All Categories" : c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="plot">Volcano Plot</TabsTrigger>
          <TabsTrigger value="table">Results Table</TabsTrigger>
        </TabsList>

        <TabsContent value="plot" className="space-y-4">
          {/* Legend */}
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-red-500" />
                  <span className="text-sm">Upregulated (p &lt; {settings.pValueThreshold}, FC &gt; {settings.log2FCThreshold})</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-blue-500" />
                  <span className="text-sm">Downregulated (p &lt; {settings.pValueThreshold}, FC &lt; -{settings.log2FCThreshold})</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full bg-gray-400" />
                  <span className="text-sm">Not Significant</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Volcano Plot */}
          <Card>
            <CardContent className="pt-6">
              <div className="h-[500px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 20, right: 30, bottom: 50, left: 50 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      type="number"
                      dataKey="x"
                      name="Log2 Fold Change"
                      domain={[-4, 4]}
                      label={{ value: "Log2 Fold Change", position: "bottom", offset: 35 }}
                    />
                    <YAxis
                      type="number"
                      dataKey="y"
                      name="-Log10(p-value)"
                      label={{ value: "-Log10(Adjusted p-value)", angle: -90, position: "left", offset: 10 }}
                    />
                    <ZAxis range={[40, 120]} />
                    <RechartsTooltip content={<CustomTooltip />} />

                    {/* Threshold lines */}
                    <ReferenceLine x={settings.log2FCThreshold} stroke="#999" strokeDasharray="3 3" />
                    <ReferenceLine x={-settings.log2FCThreshold} stroke="#999" strokeDasharray="3 3" />
                    <ReferenceLine y={-Math.log10(settings.pValueThreshold)} stroke="#999" strokeDasharray="3 3" />
                    <ReferenceLine x={0} stroke="#666" />

                    <Scatter data={plotData} fill="#8884d8">
                      {plotData.map((entry, index) => (
                        <Cell key={index} fill={getPointColor(entry, settings)} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>

              {/* Labels for top results */}
              {settings.showLabels && topResults.length > 0 && (
                <div className="mt-4 p-4 bg-muted rounded-lg">
                  <h4 className="font-medium mb-2">Top Significant Variables</h4>
                  <div className="flex flex-wrap gap-2">
                    {topResults.map(r => (
                      <Badge
                        key={r.id}
                        variant={r.significance === "upregulated" ? "destructive" : "default"}
                      >
                        {r.name} (FC: {r.log2FoldChange.toFixed(2)})
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="table" className="space-y-4">
          {/* Search */}
          <div className="relative max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search variables..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>

          {/* Results Table */}
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Variable</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead className="text-right">Log2 FC</TableHead>
                    <TableHead className="text-right">P-value</TableHead>
                    <TableHead className="text-right">Adj. P-value</TableHead>
                    <TableHead className="text-right">Base Mean</TableHead>
                    <TableHead>Significance</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {plotData
                    .sort((a, b) => a.adjustedPValue - b.adjustedPValue)
                    .slice(0, 50)
                    .map((result) => (
                      <TableRow key={result.id}>
                        <TableCell className="font-medium">{result.name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{result.category}</Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          <span className={
                            result.log2FoldChange > 0 ? "text-red-600" :
                            result.log2FoldChange < 0 ? "text-blue-600" : ""
                          }>
                            {result.log2FoldChange > 0 ? "+" : ""}{result.log2FoldChange.toFixed(3)}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatPValue(result.pValue)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          <span className={result.adjustedPValue < settings.pValueThreshold ? "font-medium" : ""}>
                            {formatPValue(result.adjustedPValue)}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {result.baseMean.toFixed(1)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={
                            result.significance === "upregulated" ? "destructive" :
                            result.significance === "downregulated" ? "default" : "secondary"
                          }>
                            {result.significance === "upregulated" && <TrendingUp className="h-3 w-3 mr-1" />}
                            {result.significance === "downregulated" && <TrendingDown className="h-3 w-3 mr-1" />}
                            {result.significance === "not_significant" && <Minus className="h-3 w-3 mr-1" />}
                            {result.significance.replace("_", " ")}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
