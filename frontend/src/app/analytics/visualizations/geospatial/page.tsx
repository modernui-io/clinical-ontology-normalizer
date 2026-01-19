"use client";

import { useState, useMemo, useCallback } from "react";
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
import { Slider } from "@/components/ui/slider";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Map,
  TrendingUp,
  TrendingDown,
  Minus,
  Search,
  Info,
  Layers,
  BarChart3,
} from "lucide-react";

// Types
interface GeospatialRegion {
  region_id: string;
  region_name: string;
  state_code: string | null;
  latitude: number;
  longitude: number;
  metric_value: number;
  metric_label: string;
  population: number;
  patient_count: number;
  confidence_interval: number[] | null;
  trend: string | null;
}

interface GeospatialData {
  regions: GeospatialRegion[];
  metric_name: string;
  metric_unit: string;
  min_value: number;
  max_value: number;
  national_average: number;
  time_period: string;
}

// API function
async function fetchGeospatialData(params: {
  metric?: string;
  condition?: string;
  timePeriod?: string;
  granularity?: string;
}): Promise<GeospatialData> {
  const searchParams = new URLSearchParams();
  if (params.metric) searchParams.set("metric", params.metric);
  if (params.condition) searchParams.set("condition", params.condition);
  if (params.timePeriod) searchParams.set("time_period", params.timePeriod);
  if (params.granularity) searchParams.set("granularity", params.granularity);

  const response = await fetch(`/api/v1/visualizations/geospatial?${searchParams.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to fetch geospatial data");
  }
  return response.json();
}

// US State paths (simplified SVG paths)
const US_STATES: Record<string, { path: string; label: { x: number; y: number } }> = {
  al: { path: "M628,388 L630,430 L605,453 L580,453 L580,388 Z", label: { x: 605, y: 420 } },
  ak: { path: "M140,450 L200,450 L200,510 L140,510 Z", label: { x: 170, y: 480 } },
  az: { path: "M208,340 L268,340 L268,420 L208,420 Z", label: { x: 238, y: 380 } },
  ar: { path: "M530,355 L590,355 L590,410 L530,410 Z", label: { x: 560, y: 382 } },
  ca: { path: "M120,220 L180,220 L200,380 L120,380 Z", label: { x: 150, y: 300 } },
  co: { path: "M290,280 L380,280 L380,340 L290,340 Z", label: { x: 335, y: 310 } },
  ct: { path: "M790,195 L810,195 L810,215 L790,215 Z", label: { x: 800, y: 205 } },
  de: { path: "M752,250 L768,250 L768,280 L752,280 Z", label: { x: 760, y: 265 } },
  fl: { path: "M640,430 L720,430 L720,520 L680,520 L640,480 Z", label: { x: 680, y: 470 } },
  ga: { path: "M640,360 L700,360 L700,430 L640,430 Z", label: { x: 670, y: 395 } },
  hi: { path: "M260,480 L320,480 L320,520 L260,520 Z", label: { x: 290, y: 500 } },
  id: { path: "M200,120 L260,120 L260,240 L200,240 Z", label: { x: 230, y: 180 } },
  il: { path: "M560,220 L600,220 L600,320 L560,320 Z", label: { x: 580, y: 270 } },
  in: { path: "M600,220 L640,220 L640,300 L600,300 Z", label: { x: 620, y: 260 } },
  ia: { path: "M480,200 L560,200 L560,260 L480,260 Z", label: { x: 520, y: 230 } },
  ks: { path: "M380,290 L480,290 L480,350 L380,350 Z", label: { x: 430, y: 320 } },
  ky: { path: "M590,290 L680,290 L680,340 L590,340 Z", label: { x: 635, y: 315 } },
  la: { path: "M530,410 L590,410 L590,470 L530,470 Z", label: { x: 560, y: 440 } },
  me: { path: "M800,80 L830,80 L830,160 L800,160 Z", label: { x: 815, y: 120 } },
  md: { path: "M720,250 L752,250 L752,280 L720,280 Z", label: { x: 736, y: 265 } },
  ma: { path: "M790,175 L830,175 L830,195 L790,195 Z", label: { x: 810, y: 185 } },
  mi: { path: "M580,120 L640,120 L640,200 L580,200 Z", label: { x: 610, y: 160 } },
  mn: { path: "M460,100 L540,100 L540,200 L460,200 Z", label: { x: 500, y: 150 } },
  ms: { path: "M575,380 L615,380 L615,460 L575,460 Z", label: { x: 595, y: 420 } },
  mo: { path: "M480,280 L560,280 L560,360 L480,360 Z", label: { x: 520, y: 320 } },
  mt: { path: "M220,80 L340,80 L340,160 L220,160 Z", label: { x: 280, y: 120 } },
  ne: { path: "M360,220 L460,220 L460,280 L360,280 Z", label: { x: 410, y: 250 } },
  nv: { path: "M160,200 L220,200 L220,340 L160,340 Z", label: { x: 190, y: 270 } },
  nh: { path: "M800,140 L820,140 L820,175 L800,175 Z", label: { x: 810, y: 157 } },
  nj: { path: "M770,210 L790,210 L790,260 L770,260 Z", label: { x: 780, y: 235 } },
  nm: { path: "M270,340 L350,340 L350,440 L270,440 Z", label: { x: 310, y: 390 } },
  ny: { path: "M720,140 L790,140 L790,220 L720,220 Z", label: { x: 755, y: 180 } },
  nc: { path: "M640,310 L760,310 L760,360 L640,360 Z", label: { x: 700, y: 335 } },
  nd: { path: "M360,80 L460,80 L460,140 L360,140 Z", label: { x: 410, y: 110 } },
  oh: { path: "M640,220 L700,220 L700,290 L640,290 Z", label: { x: 670, y: 255 } },
  ok: { path: "M380,350 L480,350 L480,400 L380,400 Z", label: { x: 430, y: 375 } },
  or: { path: "M120,120 L200,120 L200,200 L120,200 Z", label: { x: 160, y: 160 } },
  pa: { path: "M700,200 L770,200 L770,250 L700,250 Z", label: { x: 735, y: 225 } },
  ri: { path: "M810,195 L825,195 L825,210 L810,210 Z", label: { x: 817, y: 202 } },
  sc: { path: "M680,340 L740,340 L740,390 L680,390 Z", label: { x: 710, y: 365 } },
  sd: { path: "M360,140 L460,140 L460,200 L360,200 Z", label: { x: 410, y: 170 } },
  tn: { path: "M560,320 L680,320 L680,360 L560,360 Z", label: { x: 620, y: 340 } },
  tx: { path: "M320,380 L480,380 L480,520 L320,520 Z", label: { x: 400, y: 450 } },
  ut: { path: "M220,220 L290,220 L290,340 L220,340 Z", label: { x: 255, y: 280 } },
  vt: { path: "M780,130 L800,130 L800,170 L780,170 Z", label: { x: 790, y: 150 } },
  va: { path: "M680,270 L760,270 L760,320 L680,320 Z", label: { x: 720, y: 295 } },
  wa: { path: "M120,60 L200,60 L200,120 L120,120 Z", label: { x: 160, y: 90 } },
  wv: { path: "M680,250 L720,250 L720,300 L680,300 Z", label: { x: 700, y: 275 } },
  wi: { path: "M540,120 L600,120 L600,200 L540,200 Z", label: { x: 570, y: 160 } },
  wy: { path: "M260,160 L360,160 L360,240 L260,240 Z", label: { x: 310, y: 200 } },
};

// Color scale
function getColor(value: number, min: number, max: number): string {
  const normalized = (value - min) / (max - min);
  // Blue to Red gradient
  const r = Math.round(normalized * 220 + 35);
  const g = Math.round((1 - normalized) * 140 + 80);
  const b = Math.round((1 - normalized) * 220 + 35);
  return `rgb(${r}, ${g}, ${b})`;
}

// Trend icon
function TrendIcon({ trend }: { trend: string | null }) {
  if (trend === "increasing") return <TrendingUp className="h-4 w-4 text-red-500" />;
  if (trend === "decreasing") return <TrendingDown className="h-4 w-4 text-green-500" />;
  return <Minus className="h-4 w-4 text-gray-400" />;
}

export default function GeospatialPage() {
  // State
  const [metric, setMetric] = useState("prevalence");
  const [condition, setCondition] = useState("diabetes");
  const [timePeriod, setTimePeriod] = useState("2024");
  const [granularity, setGranularity] = useState("state");
  const [searchQuery, setSearchQuery] = useState("");
  const [hoveredRegion, setHoveredRegion] = useState<GeospatialRegion | null>(null);
  const [selectedRegion, setSelectedRegion] = useState<GeospatialRegion | null>(null);

  // Fetch data
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["geospatial", metric, condition, timePeriod, granularity],
    queryFn: () => fetchGeospatialData({ metric, condition, timePeriod, granularity }),
  });

  // Filter regions
  const filteredRegions = useMemo(() => {
    if (!data) return [];
    if (!searchQuery) return data.regions;
    return data.regions.filter(
      (r) =>
        r.region_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.state_code?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [data, searchQuery]);

  // Sort regions by metric value
  const sortedRegions = useMemo(() => {
    return [...filteredRegions].sort((a, b) => b.metric_value - a.metric_value);
  }, [filteredRegions]);

  // Statistics
  const stats = useMemo(() => {
    if (!data) return null;
    const values = data.regions.map((r) => r.metric_value);
    const totalPatients = data.regions.reduce((sum, r) => sum + r.patient_count, 0);
    const totalPopulation = data.regions.reduce((sum, r) => sum + r.population, 0);
    return {
      min: Math.min(...values),
      max: Math.max(...values),
      avg: values.reduce((a, b) => a + b, 0) / values.length,
      totalPatients,
      totalPopulation,
      aboveAvg: data.regions.filter((r) => r.metric_value > data.national_average).length,
    };
  }, [data]);

  // Handle export
  const handleExport = useCallback(() => {
    if (!data) return;
    const exportData = {
      metric_name: data.metric_name,
      time_period: data.time_period,
      regions: data.regions.map((r) => ({
        state: r.state_code,
        name: r.region_name,
        value: r.metric_value,
        patients: r.patient_count,
        population: r.population,
        trend: r.trend,
      })),
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `geospatial-${condition}-${metric}-${timePeriod}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data, condition, metric, timePeriod]);

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
              <Map className="h-6 w-6" />
              Geospatial Health Mapping
            </h1>
            <p className="text-muted-foreground">
              Regional health metrics and disease prevalence mapping
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export Data
          </Button>
        </div>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Layers className="h-4 w-4" />
            Map Settings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-5">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Condition</label>
              <Select value={condition} onValueChange={setCondition}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="diabetes">Diabetes</SelectItem>
                  <SelectItem value="hypertension">Hypertension</SelectItem>
                  <SelectItem value="obesity">Obesity</SelectItem>
                  <SelectItem value="heart_disease">Heart Disease</SelectItem>
                  <SelectItem value="cancer">Cancer</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Metric</label>
              <Select value={metric} onValueChange={setMetric}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="prevalence">Prevalence</SelectItem>
                  <SelectItem value="incidence">Incidence</SelectItem>
                  <SelectItem value="mortality">Mortality</SelectItem>
                  <SelectItem value="outcomes">Outcomes</SelectItem>
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
                  <SelectItem value="2024">2024</SelectItem>
                  <SelectItem value="2023">2023</SelectItem>
                  <SelectItem value="2022">2022</SelectItem>
                  <SelectItem value="2021">2021</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Granularity</label>
              <Select value={granularity} onValueChange={setGranularity}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="state">State</SelectItem>
                  <SelectItem value="county">County</SelectItem>
                  <SelectItem value="zip">ZIP Code</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Search</label>
              <div className="relative mt-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search regions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Map */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{data?.metric_name || "Health Metric Map"}</CardTitle>
                <CardDescription>
                  {data ? `${data.time_period} - ${data.regions.length} regions` : "Loading..."}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <p>Failed to load map data</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
                  Retry
                </Button>
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-24">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : data ? (
              <div className="relative">
                {/* SVG Map */}
                <svg
                  viewBox="100 50 750 500"
                  className="w-full h-auto"
                  style={{ maxHeight: "500px" }}
                >
                  {/* States */}
                  {data.regions.map((region) => {
                    const stateData = US_STATES[region.region_id];
                    if (!stateData) return null;

                    const isHovered = hoveredRegion?.region_id === region.region_id;
                    const isSelected = selectedRegion?.region_id === region.region_id;

                    return (
                      <g key={region.region_id}>
                        <path
                          d={stateData.path}
                          fill={getColor(region.metric_value, data.min_value, data.max_value)}
                          stroke={isSelected ? "#000" : isHovered ? "#666" : "#fff"}
                          strokeWidth={isSelected ? 2 : isHovered ? 1.5 : 0.5}
                          opacity={isHovered || isSelected ? 1 : 0.85}
                          style={{ cursor: "pointer", transition: "all 0.15s" }}
                          onMouseEnter={() => setHoveredRegion(region)}
                          onMouseLeave={() => setHoveredRegion(null)}
                          onClick={() => setSelectedRegion(region)}
                        />
                        <text
                          x={stateData.label.x}
                          y={stateData.label.y}
                          textAnchor="middle"
                          dominantBaseline="middle"
                          fontSize="8"
                          fill="#fff"
                          fontWeight="bold"
                          style={{ pointerEvents: "none" }}
                        >
                          {region.state_code}
                        </text>
                      </g>
                    );
                  })}
                </svg>

                {/* Tooltip */}
                {hoveredRegion && (
                  <div className="absolute top-4 right-4 bg-popover border rounded-lg shadow-lg p-3 text-sm min-w-[180px]">
                    <div className="font-medium">{hoveredRegion.region_name}</div>
                    <div className="text-2xl font-bold mt-1">{hoveredRegion.metric_label}</div>
                    <div className="flex items-center gap-2 mt-2 text-muted-foreground">
                      <TrendIcon trend={hoveredRegion.trend} />
                      <span className="capitalize">{hoveredRegion.trend || "stable"}</span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {hoveredRegion.patient_count.toLocaleString()} patients
                    </div>
                  </div>
                )}

                {/* Legend */}
                <div className="mt-4 flex items-center justify-center gap-4">
                  <span className="text-xs text-muted-foreground">Low ({data.min_value.toFixed(1)}%)</span>
                  <div className="w-32 h-3 rounded" style={{
                    background: `linear-gradient(to right, ${getColor(data.min_value, data.min_value, data.max_value)}, ${getColor(data.max_value, data.min_value, data.max_value)})`
                  }} />
                  <span className="text-xs text-muted-foreground">High ({data.max_value.toFixed(1)}%)</span>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Summary Stats */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <BarChart3 className="h-4 w-4" />
                Summary Statistics
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {stats && data && (
                <>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">National Average</span>
                    <span className="font-medium">{data.national_average.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Range</span>
                    <span className="font-medium">
                      {stats.min.toFixed(1)}% - {stats.max.toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Above Average</span>
                    <span className="font-medium">{stats.aboveAvg} states</span>
                  </div>
                  <div className="border-t pt-3 mt-3">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Patients</span>
                      <span className="font-medium">{stats.totalPatients.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-muted-foreground">Total Population</span>
                      <span className="font-medium">{(stats.totalPopulation / 1000000).toFixed(1)}M</span>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Selected Region Details */}
          {selectedRegion && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">{selectedRegion.region_name}</CardTitle>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedRegion(null)}>
                    Clear
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-center py-2">
                  <div className="text-4xl font-bold">{selectedRegion.metric_label}</div>
                  <div className="flex items-center justify-center gap-2 mt-2">
                    <TrendIcon trend={selectedRegion.trend} />
                    <span className="text-sm text-muted-foreground capitalize">
                      {selectedRegion.trend || "stable"} trend
                    </span>
                  </div>
                </div>
                <div className="border-t pt-3 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Patient Count</span>
                    <span className="font-medium">{selectedRegion.patient_count.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Population</span>
                    <span className="font-medium">{selectedRegion.population.toLocaleString()}</span>
                  </div>
                  {selectedRegion.confidence_interval && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">95% CI</span>
                      <span className="font-medium">
                        {selectedRegion.confidence_interval[0].toFixed(1)}% -{" "}
                        {selectedRegion.confidence_interval[1].toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Top/Bottom Regions */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Regional Rankings</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-2">Highest</div>
                  {sortedRegions.slice(0, 5).map((region) => (
                    <div
                      key={region.region_id}
                      className="flex items-center justify-between py-1.5 text-sm hover:bg-muted/50 rounded px-2 cursor-pointer"
                      onClick={() => setSelectedRegion(region)}
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-sm"
                          style={{ backgroundColor: getColor(region.metric_value, data?.min_value || 0, data?.max_value || 10) }}
                        />
                        <span>{region.region_name}</span>
                      </div>
                      <span className="font-medium">{region.metric_label}</span>
                    </div>
                  ))}
                </div>
                <div className="border-t pt-4">
                  <div className="text-xs font-medium text-muted-foreground mb-2">Lowest</div>
                  {sortedRegions.slice(-5).reverse().map((region) => (
                    <div
                      key={region.region_id}
                      className="flex items-center justify-between py-1.5 text-sm hover:bg-muted/50 rounded px-2 cursor-pointer"
                      onClick={() => setSelectedRegion(region)}
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-sm"
                          style={{ backgroundColor: getColor(region.metric_value, data?.min_value || 0, data?.max_value || 10) }}
                        />
                        <span>{region.region_name}</span>
                      </div>
                      <span className="font-medium">{region.metric_label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Data Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Regional Data Table
          </CardTitle>
          <CardDescription>
            Showing {filteredRegions.length} of {data?.regions.length || 0} regions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>State</TableHead>
                  <TableHead>Region</TableHead>
                  <TableHead className="text-right">Metric Value</TableHead>
                  <TableHead className="text-right">Patients</TableHead>
                  <TableHead className="text-right">Population</TableHead>
                  <TableHead className="text-right">95% CI</TableHead>
                  <TableHead className="text-center">Trend</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedRegions.slice(0, 20).map((region) => (
                  <TableRow
                    key={region.region_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedRegion(region)}
                  >
                    <TableCell>
                      <Badge variant="outline">{region.state_code}</Badge>
                    </TableCell>
                    <TableCell className="font-medium">{region.region_name}</TableCell>
                    <TableCell className="text-right font-medium">{region.metric_label}</TableCell>
                    <TableCell className="text-right">{region.patient_count.toLocaleString()}</TableCell>
                    <TableCell className="text-right">{(region.population / 1000000).toFixed(2)}M</TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {region.confidence_interval
                        ? `${region.confidence_interval[0].toFixed(1)} - ${region.confidence_interval[1].toFixed(1)}`
                        : "-"}
                    </TableCell>
                    <TableCell className="text-center">
                      <TrendIcon trend={region.trend} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
