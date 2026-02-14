"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
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
  ArrowRight,
  GitBranch,
  Activity,
  Map,
  BarChart2,
  TrendingUp,
  Users,
  Microscope,
  Loader2,
  AlertCircle,
  CheckCircle,
  RefreshCw,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types for backend visualization responses (lightweight subset)
// ---------------------------------------------------------------------------

interface VizEndpointStatus {
  available: boolean;
  count: number;
  label: string;
  loading: boolean;
  error: string | null;
}

interface VizStats {
  sankey: VizEndpointStatus;
  survival: VizEndpointStatus;
  geospatial: VizEndpointStatus;
  forest: VizEndpointStatus;
  volcano: VizEndpointStatus;
  timeline: VizEndpointStatus;
}

// Maps visualization card ids to which backend endpoints they cover
const vizEndpointMap: Record<string, (keyof VizStats)[]> = {
  pathways: ["sankey"],
  survival: ["survival"],
  geospatial: ["geospatial"],
  research: ["forest", "volcano", "timeline"],
};

function defaultEndpointStatus(label: string): VizEndpointStatus {
  return { available: false, count: 0, label, loading: true, error: null };
}

function defaultVizStats(): VizStats {
  return {
    sankey: defaultEndpointStatus("Patients"),
    survival: defaultEndpointStatus("Cohorts"),
    geospatial: defaultEndpointStatus("Regions"),
    forest: defaultEndpointStatus("Studies"),
    volcano: defaultEndpointStatus("Features"),
    timeline: defaultEndpointStatus("Events"),
  };
}

// ---------------------------------------------------------------------------
// Visualization categories (static layout data)
// ---------------------------------------------------------------------------

const visualizations = [
  {
    id: "pathways",
    title: "Treatment Pathways",
    description:
      "Sankey diagrams showing patient flow through treatment stages and outcomes. Visualize how patients progress from diagnosis through treatment options.",
    icon: GitBranch,
    href: "/analytics/visualizations/pathways",
    category: "Clinical",
    features: [
      "Patient flow analysis",
      "Treatment sequences",
      "Outcome tracking",
      "Cohort filtering",
    ],
    preview: (
      <div className="h-32 bg-gradient-to-r from-blue-500/20 via-purple-500/20 to-green-500/20 rounded-lg flex items-center justify-center">
        <div className="flex items-center gap-2">
          <div className="w-12 h-8 bg-blue-500/40 rounded" />
          <div className="flex flex-col gap-1">
            <div className="w-16 h-3 bg-purple-500/30 rounded" />
            <div className="w-16 h-3 bg-purple-500/30 rounded" />
          </div>
          <div className="w-12 h-8 bg-green-500/40 rounded" />
        </div>
      </div>
    ),
  },
  {
    id: "survival",
    title: "Survival Analysis",
    description:
      "Kaplan-Meier survival curves for cohort comparison with confidence intervals, log-rank tests, and hazard ratios.",
    icon: Activity,
    href: "/analytics/visualizations/survival",
    category: "Clinical",
    features: [
      "Multiple cohorts",
      "Confidence intervals",
      "Risk tables",
      "Statistical tests",
    ],
    preview: (
      <div className="h-32 bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 rounded-lg p-4">
        <svg viewBox="0 0 100 60" className="w-full h-full">
          <path
            d="M0,5 L20,5 L20,15 L40,15 L40,25 L60,25 L60,40 L80,40 L80,55 L100,55"
            fill="none"
            stroke="rgb(16, 185, 129)"
            strokeWidth="2"
          />
          <path
            d="M0,5 L15,8 L30,20 L45,35 L60,45 L75,50 L90,52 L100,55"
            fill="none"
            stroke="rgb(239, 68, 68)"
            strokeWidth="2"
            strokeDasharray="4,2"
          />
        </svg>
      </div>
    ),
  },
  {
    id: "geospatial",
    title: "Geospatial Health Mapping",
    description:
      "Choropleth maps showing regional health metrics, disease prevalence, and outcome variations across geographic areas.",
    icon: Map,
    href: "/analytics/visualizations/geospatial",
    category: "Population Health",
    features: [
      "State/county level",
      "Multiple metrics",
      "Time slider",
      "Drill-down capability",
    ],
    preview: (
      <div className="h-32 bg-gradient-to-br from-blue-500/10 to-blue-500/5 rounded-lg p-4 flex items-center justify-center">
        <div className="grid grid-cols-4 gap-1">
          {[...Array(16)].map((_, i) => (
            <div
              key={i}
              className="w-6 h-4 rounded-sm"
              style={{
                backgroundColor: `rgba(59, 130, 246, ${0.2 + Math.random() * 0.6})`,
              }}
            />
          ))}
        </div>
      </div>
    ),
  },
  {
    id: "research",
    title: "Research Plots",
    description:
      "Forest plots for meta-analysis, volcano plots for differential analysis, and Gantt charts for study timelines.",
    icon: Microscope,
    href: "/analytics/visualizations/research",
    category: "Research",
    features: [
      "Forest plots",
      "Volcano plots",
      "Study timelines",
      "Effect size analysis",
    ],
    preview: (
      <div className="h-32 bg-gradient-to-br from-amber-500/10 to-amber-500/5 rounded-lg p-4">
        <div className="flex flex-col gap-2">
          {[0.7, 0.85, 0.65, 0.9].map((val, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className="w-16 text-[8px] text-muted-foreground truncate">
                Study {i + 1}
              </div>
              <div className="flex-1 h-2 bg-muted rounded relative">
                <div
                  className="absolute h-4 w-0.5 bg-amber-500 -top-1"
                  style={{ left: `${val * 100}%` }}
                />
                <div
                  className="absolute h-2 bg-amber-500/30 top-0"
                  style={{ left: `${(val - 0.15) * 100}%`, width: "30%" }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
];

// ---------------------------------------------------------------------------
// Data-fetching helpers
// ---------------------------------------------------------------------------

async function fetchEndpointStatus(
  endpoint: keyof VizStats,
): Promise<VizEndpointStatus> {
  const urlMap: Record<keyof VizStats, string> = {
    sankey: "/api/visualizations/sankey",
    survival: "/api/visualizations/survival",
    geospatial: "/api/visualizations/geospatial",
    forest: "/api/visualizations/forest",
    volcano: "/api/visualizations/volcano",
    timeline: "/api/visualizations/timeline",
  };

  const labelMap: Record<keyof VizStats, string> = {
    sankey: "Patients",
    survival: "Cohorts",
    geospatial: "Regions",
    forest: "Studies",
    volcano: "Features",
    timeline: "Events",
  };

  try {
    const res = await fetch(urlMap[endpoint], { signal: AbortSignal.timeout(8000) });
    if (!res.ok) {
      return {
        available: false,
        count: 0,
        label: labelMap[endpoint],
        loading: false,
        error: `HTTP ${res.status}`,
      };
    }
    const data = await res.json();

    // Extract a meaningful count depending on the endpoint shape
    let count = 0;
    let available = false;

    switch (endpoint) {
      case "sankey":
        count = data.total_patients ?? 0;
        available = (data.nodes?.length ?? 0) > 0;
        break;
      case "survival":
        count = data.curves?.length ?? 0;
        available = count > 0;
        break;
      case "geospatial":
        count = data.regions?.length ?? 0;
        available = count > 0;
        break;
      case "forest":
        count = data.studies?.length ?? 0;
        available = count > 0;
        break;
      case "volcano":
        count = data.total_features ?? 0;
        available = (data.points?.length ?? 0) > 0;
        break;
      case "timeline":
        count = data.events?.length ?? 0;
        available = count > 0;
        break;
    }

    return {
      available,
      count,
      label: labelMap[endpoint],
      loading: false,
      error: null,
    };
  } catch (err) {
    return {
      available: false,
      count: 0,
      label: labelMap[endpoint],
      loading: false,
      error: err instanceof Error ? err.message : "Fetch failed",
    };
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function VisualizationsGalleryPage() {
  const [vizStats, setVizStats] = useState<VizStats>(defaultVizStats);
  const [globalLoading, setGlobalLoading] = useState(true);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const fetchAllStats = useCallback(async () => {
    setGlobalLoading(true);
    setGlobalError(null);
    // Reset all to loading
    setVizStats(defaultVizStats());

    const endpoints: (keyof VizStats)[] = [
      "sankey",
      "survival",
      "geospatial",
      "forest",
      "volcano",
      "timeline",
    ];

    const results = await Promise.allSettled(
      endpoints.map((ep) => fetchEndpointStatus(ep)),
    );

    const next = defaultVizStats();
    let anySuccess = false;
    let allFailed = true;

    results.forEach((result, i) => {
      const ep = endpoints[i];
      if (result.status === "fulfilled") {
        next[ep] = result.value;
        if (!result.value.error) anySuccess = true;
        if (!result.value.error) allFailed = false;
      } else {
        next[ep] = {
          available: false,
          count: 0,
          label: next[ep].label,
          loading: false,
          error: "Request failed",
        };
      }
    });

    setVizStats(next);
    setGlobalLoading(false);
    if (allFailed && !anySuccess) {
      setGlobalError("Unable to connect to the visualization service. The backend may be offline.");
    }
  }, []);

  useEffect(() => {
    fetchAllStats();
  }, [fetchAllStats]);

  // Compute quick stats from live data
  const totalPatients = vizStats.sankey.count;
  const totalCohorts = vizStats.survival.count;
  const totalStudies = vizStats.forest.count;
  const totalRegions = vizStats.geospatial.count;

  const quickStats = [
    {
      label: "Visualization Types",
      value: "6",
      icon: BarChart2,
      loading: false,
    },
    {
      label: "Active Cohorts",
      value: globalLoading ? "..." : String(totalCohorts),
      icon: Users,
      loading: vizStats.survival.loading,
    },
    {
      label: "Studies Tracked",
      value: globalLoading ? "..." : String(totalStudies),
      icon: Microscope,
      loading: vizStats.forest.loading,
    },
    {
      label: "Regions Mapped",
      value: globalLoading ? "..." : String(totalRegions),
      icon: Map,
      loading: vizStats.geospatial.loading,
    },
  ];

  // Derive card-level availability from its mapped endpoints
  function getCardStatus(vizId: string) {
    const endpoints = vizEndpointMap[vizId] ?? [];
    const statuses = endpoints.map((ep) => vizStats[ep]);

    const anyLoading = statuses.some((s) => s.loading);
    const anyAvailable = statuses.some((s) => s.available);
    const anyError = statuses.some((s) => s.error !== null);
    const allError = statuses.every((s) => s.error !== null);

    return { anyLoading, anyAvailable, anyError, allError, statuses };
  }

  function renderDataBadge(vizId: string) {
    const { anyLoading, anyAvailable, anyError, allError, statuses } =
      getCardStatus(vizId);

    if (anyLoading) {
      return (
        <Badge variant="secondary" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          Checking...
        </Badge>
      );
    }

    if (allError) {
      return (
        <Badge variant="destructive" className="gap-1">
          <AlertCircle className="h-3 w-3" />
          Unavailable
        </Badge>
      );
    }

    if (anyAvailable) {
      // Build summary string: e.g. "142 patients" or "8 studies, 50 features, 12 events"
      const parts = statuses
        .filter((s) => s.available && s.count > 0)
        .map((s) => `${s.count} ${s.label.toLowerCase()}`);
      return (
        <Badge className="gap-1 bg-emerald-600 hover:bg-emerald-700">
          <CheckCircle className="h-3 w-3" />
          {parts.length > 0 ? parts.join(", ") : "Data Available"}
        </Badge>
      );
    }

    if (anyError) {
      return (
        <Badge variant="outline" className="gap-1 text-amber-600 border-amber-400">
          <AlertCircle className="h-3 w-3" />
          Partial Error
        </Badge>
      );
    }

    return (
      <Badge variant="outline" className="gap-1 text-amber-600 border-amber-400">
        No Data
      </Badge>
    );
  }

  return (
    <div className="p-6 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Advanced Visualization Suite
          </h1>
          <p className="text-muted-foreground mt-1">
            Interactive clinical analytics and research visualizations
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchAllStats}
            disabled={globalLoading}
          >
            {globalLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Refresh Data
          </Button>
          <Button variant="outline">
            <TrendingUp className="mr-2 h-4 w-4" />
            View Reports
          </Button>
        </div>
      </div>

      {/* Global error banner */}
      {globalError && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-3 p-4">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0" />
            <div className="text-sm">
              <p className="font-medium text-destructive">{globalError}</p>
              <p className="text-muted-foreground mt-0.5">
                Ensure the backend is running at the configured address and try
                refreshing.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        {quickStats.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="flex items-center gap-4 p-4">
              <div className="rounded-lg bg-primary/10 p-2.5">
                {stat.loading ? (
                  <Loader2 className="h-5 w-5 text-primary animate-spin" />
                ) : (
                  <stat.icon className="h-5 w-5 text-primary" />
                )}
              </div>
              <div>
                <div className="text-2xl font-bold">{stat.value}</div>
                <div className="text-xs text-muted-foreground">
                  {stat.label}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Visualization Cards */}
      <div className="grid gap-6 md:grid-cols-2">
        {visualizations.map((viz) => (
          <Card
            key={viz.id}
            className="overflow-hidden hover:shadow-lg transition-shadow"
          >
            <CardHeader className="pb-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-primary/10 p-2.5">
                    <viz.icon className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">{viz.title}</CardTitle>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="secondary">{viz.category}</Badge>
                      {renderDataBadge(viz.id)}
                    </div>
                  </div>
                </div>
              </div>
              <CardDescription className="mt-3">
                {viz.description}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Preview */}
              {viz.preview}

              {/* Features */}
              <div className="flex flex-wrap gap-2">
                {viz.features.map((feature) => (
                  <Badge key={feature} variant="outline" className="text-xs">
                    {feature}
                  </Badge>
                ))}
              </div>

              {/* Action */}
              <Link href={viz.href}>
                <Button className="w-full">
                  Open Visualization
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Additional Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart2 className="h-5 w-5" />
            About the Visualization Suite
          </CardTitle>
        </CardHeader>
        <CardContent className="prose prose-sm dark:prose-invert max-w-none">
          <p>
            The Advanced Visualization Suite provides interactive,
            publication-ready visualizations for clinical research and healthcare
            analytics. All visualizations support:
          </p>
          <ul className="grid gap-2 md:grid-cols-2 list-none pl-0">
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Export to SVG/PNG for publications
            </li>
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Interactive tooltips and drill-down
            </li>
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Cohort and time period filtering
            </li>
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Real-time data updates
            </li>
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Responsive design for all devices
            </li>
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Statistical annotations
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
