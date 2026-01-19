"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  GitBranch,
  Users,
  Filter,
  Info,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Sankey, Rectangle, Layer, ResponsiveContainer } from "recharts";

// Types
interface SankeyNode {
  id: string;
  name: string;
  category: string;
  value: number;
}

interface SankeyLink {
  source: string;
  target: string;
  value: number;
}

interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
  total_patients: number;
}

// API function
async function fetchSankeyData(params: {
  cohortId?: string;
  timePeriod?: string;
  pathwayType?: string;
}): Promise<SankeyData> {
  const searchParams = new URLSearchParams();
  if (params.cohortId) searchParams.set("cohort_id", params.cohortId);
  if (params.timePeriod) searchParams.set("time_period", params.timePeriod);
  if (params.pathwayType) searchParams.set("pathway_type", params.pathwayType);

  const response = await fetch(`/api/v1/visualizations/sankey?${searchParams.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to fetch Sankey data");
  }
  return response.json();
}

// Category colors
const CATEGORY_COLORS: Record<string, string> = {
  diagnosis: "#3b82f6", // blue
  first_line: "#8b5cf6", // purple
  second_line: "#f59e0b", // amber
  outcome: "#10b981", // emerald
};

// Custom Sankey node component
function CustomSankeyNode({
  x = 0,
  y = 0,
  width = 0,
  height = 0,
  payload = { name: "", category: "", value: 0 },
  onNodeClick,
}: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  index?: number;
  payload?: { name: string; category: string; value: number };
  onNodeClick?: (node: { name: string; category: string; value: number }) => void;
}) {
  const color = CATEGORY_COLORS[payload.category] || "#6b7280";

  return (
    <g>
      <Rectangle
        x={x}
        y={y}
        width={width}
        height={height}
        fill={color}
        fillOpacity={0.9}
        rx={3}
        ry={3}
        style={{ cursor: "pointer" }}
        onClick={() => onNodeClick?.(payload)}
      />
      <text
        x={x + width / 2}
        y={y + height / 2}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={11}
        fill="#fff"
        fontWeight={500}
        style={{ pointerEvents: "none" }}
      >
        {payload.name.length > 12 ? `${payload.name.slice(0, 12)}...` : payload.name}
      </text>
      <text
        x={x + width / 2}
        y={y + height + 14}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={10}
        fill="#6b7280"
      >
        {payload.value.toLocaleString()}
      </text>
    </g>
  );
}

// Custom Sankey link component
function CustomSankeyLink({
  sourceX = 0,
  targetX = 0,
  sourceY = 0,
  targetY = 0,
  sourceControlX = 0,
  targetControlX = 0,
  linkWidth = 1,
  payload = { source: { category: "" }, value: 0 },
}: {
  sourceX?: number;
  targetX?: number;
  sourceY?: number;
  targetY?: number;
  sourceControlX?: number;
  targetControlX?: number;
  linkWidth?: number;
  payload?: { source: { category: string }; value: number };
}) {
  const color = CATEGORY_COLORS[payload.source?.category] || "#6b7280";

  return (
    <path
      d={`
        M${sourceX},${sourceY}
        C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}
      `}
      fill="none"
      stroke={color}
      strokeWidth={linkWidth}
      strokeOpacity={0.4}
      style={{ transition: "stroke-opacity 0.2s" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.strokeOpacity = "0.7";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.strokeOpacity = "0.4";
      }}
    />
  );
}

export default function TreatmentPathwaysPage() {
  // Filter state
  const [pathwayType, setPathwayType] = useState("treatment");
  const [timePeriod, setTimePeriod] = useState("all");
  const [cohortId, setCohortId] = useState<string | undefined>();
  const [selectedNode, setSelectedNode] = useState<SankeyNode | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);

  // Fetch data
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["sankey", pathwayType, timePeriod, cohortId],
    queryFn: () =>
      fetchSankeyData({
        pathwayType,
        timePeriod: timePeriod !== "all" ? timePeriod : undefined,
        cohortId,
      }),
  });

  // Transform data for Recharts Sankey
  const sankeyData = useMemo(() => {
    if (!data) return null;

    // Create node index map
    const nodeIndexMap = new Map<string, number>();
    data.nodes.forEach((node, index) => {
      nodeIndexMap.set(node.id, index);
    });

    // Transform nodes
    const nodes = data.nodes.map((node) => ({
      name: node.name,
      category: node.category,
      value: node.value,
    }));

    // Transform links with numeric indices
    const links = data.links
      .map((link) => ({
        source: nodeIndexMap.get(link.source) ?? -1,
        target: nodeIndexMap.get(link.target) ?? -1,
        value: link.value,
      }))
      .filter((link) => link.source >= 0 && link.target >= 0);

    return { nodes, links };
  }, [data]);

  // Handle node click
  const handleNodeClick = useCallback((node: { name: string; category: string; value: number }) => {
    setSelectedNode(node as SankeyNode);
  }, []);

  // Handle export
  const handleExport = useCallback((format: "svg" | "png") => {
    const svgElement = document.querySelector(".sankey-chart svg");
    if (!svgElement) return;

    if (format === "svg") {
      const svgData = new XMLSerializer().serializeToString(svgElement);
      const blob = new Blob([svgData], { type: "image/svg+xml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `treatment-pathways-${new Date().toISOString().split("T")[0]}.svg`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      // PNG export would require canvas conversion
      alert("PNG export coming soon. Use SVG for now.");
    }
  }, []);

  // Category stats
  const categoryStats = useMemo(() => {
    if (!data) return [];
    const stats: Record<string, { count: number; patients: number }> = {};
    data.nodes.forEach((node) => {
      if (!stats[node.category]) {
        stats[node.category] = { count: 0, patients: 0 };
      }
      stats[node.category].count++;
      stats[node.category].patients += node.value;
    });
    return Object.entries(stats).map(([category, { count, patients }]) => ({
      category,
      count,
      patients,
    }));
  }, [data]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/analytics/visualizations">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <GitBranch className="h-6 w-6" />
              Treatment Pathway Analysis
            </h1>
            <p className="text-muted-foreground">
              Visualize patient flow through diagnosis, treatment, and outcomes
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleExport("svg")}>
            <Download className="mr-2 h-4 w-4" />
            Export SVG
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Pathway Type</label>
              <Select value={pathwayType} onValueChange={setPathwayType}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="treatment">Treatment Pathways</SelectItem>
                  <SelectItem value="diagnosis">Diagnostic Journey</SelectItem>
                  <SelectItem value="care">Care Transitions</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Time Period</label>
              <Select value={timePeriod} onValueChange={setTimePeriod}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Time</SelectItem>
                  <SelectItem value="2024">2024</SelectItem>
                  <SelectItem value="2023">2023</SelectItem>
                  <SelectItem value="Q1-2024">Q1 2024</SelectItem>
                  <SelectItem value="Q2-2024">Q2 2024</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Zoom</label>
              <div className="flex items-center gap-2 mt-1">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setZoomLevel(Math.max(0.5, zoomLevel - 0.1))}
                >
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <span className="text-sm font-medium w-12 text-center">
                  {Math.round(zoomLevel * 100)}%
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setZoomLevel(Math.min(2, zoomLevel + 0.1))}
                >
                  <ZoomIn className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="flex items-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setPathwayType("treatment");
                  setTimePeriod("all");
                  setZoomLevel(1);
                }}
              >
                Reset Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-4">
        {/* Sankey Chart */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Patient Flow Diagram</CardTitle>
                <CardDescription>
                  {data
                    ? `${data.total_patients.toLocaleString()} patients across ${data.nodes.length} stages`
                    : "Loading..."}
                </CardDescription>
              </div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon">
                      <Info className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p>
                      Click on nodes to see details. Flow width represents patient count.
                      Colors indicate treatment stage.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <p>Failed to load pathway data</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
                  Retry
                </Button>
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-24">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : sankeyData && sankeyData.links.length > 0 ? (
              <div
                className="sankey-chart overflow-auto"
                style={{ transform: `scale(${zoomLevel})`, transformOrigin: "top left" }}
              >
                <ResponsiveContainer width="100%" height={500 * zoomLevel}>
                  <Sankey
                    data={sankeyData}
                    nodePadding={40}
                    nodeWidth={20}
                    linkCurvature={0.5}
                    iterations={64}
                    node={<CustomSankeyNode onNodeClick={handleNodeClick} />}
                    link={<CustomSankeyLink />}
                    margin={{ top: 20, right: 200, bottom: 40, left: 20 }}
                  >
                  </Sankey>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
                <GitBranch className="h-12 w-12 mb-4 opacity-50" />
                <p>No pathway data available</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Legend */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Legend</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {Object.entries(CATEGORY_COLORS).map(([category, color]) => (
                <div key={category} className="flex items-center gap-2">
                  <div
                    className="w-4 h-4 rounded"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-sm capitalize">{category.replace("_", " ")}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Category Stats */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Stage Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {categoryStats.map((stat) => (
                <div key={stat.category} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded"
                      style={{ backgroundColor: CATEGORY_COLORS[stat.category] }}
                    />
                    <span className="text-sm capitalize">
                      {stat.category.replace("_", " ")}
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium">{stat.count} nodes</div>
                    <div className="text-xs text-muted-foreground">
                      {stat.patients.toLocaleString()} patients
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Selected Node Details */}
          {selectedNode && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Selected Node</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div>
                    <div className="text-sm font-medium">{selectedNode.name}</div>
                    <Badge
                      variant="outline"
                      className="mt-1"
                      style={{
                        borderColor: CATEGORY_COLORS[selectedNode.category],
                        color: CATEGORY_COLORS[selectedNode.category],
                      }}
                    >
                      {selectedNode.category.replace("_", " ")}
                    </Badge>
                  </div>
                  <div className="pt-2 border-t">
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm">
                        {selectedNode.value.toLocaleString()} patients
                      </span>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full mt-2"
                    onClick={() => setSelectedNode(null)}
                  >
                    Clear Selection
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Total Patients */}
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <div className="text-3xl font-bold text-primary">
                  {data?.total_patients.toLocaleString() || "---"}
                </div>
                <div className="text-sm text-muted-foreground">Total Patients</div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
