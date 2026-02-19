"use client";

import { useState, useEffect, useCallback } from "react";
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
import {
  FileText,
  Users,
  Activity,
  Clock,
  CheckCircle,
  AlertCircle,
  Upload,
  Search,
  ArrowRight,
  TrendingUp,
  BarChart3,
  RefreshCw,
  FlaskConical,
} from "lucide-react";
import { PersonaNavigator } from "@/components/PersonaNavigator";
import { useAuth } from "@/hooks/use-auth";
import { DEMO_DASHBOARD_STATS, DEMO_RECENT_ACTIVITY } from "@/lib/demo-data";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";

interface DashboardStats {
  totalDocuments: number;
  totalPatients: number;
  activeTrials: number;
  completedDocs: number;
  processingDocs: number;
  failedDocs: number;
}

interface RecentActivity {
  id: string;
  type: "document_uploaded" | "document_processed" | "patient_added" | "job_completed" | "job_failed";
  title: string;
  description: string;
  timestamp: string;
  patientId?: string;
  documentId?: string;
}

function formatTimeAgo(isoTimestamp: string): string {
  const now = Date.now();
  const then = new Date(isoTimestamp).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function mapAuditAction(action: string, resourceType: string): RecentActivity["type"] {
  if (action === "create" && resourceType === "document") return "document_uploaded";
  if (action === "read" && resourceType === "document") return "document_processed";
  if (action === "create" && resourceType === "patient") return "patient_added";
  if (action === "create" && resourceType === "system") return "job_completed";
  if (resourceType === "patient") return "patient_added";
  if (resourceType === "document") return "document_processed";
  return "job_completed";
}

function describeAuditLog(log: { action: string; resource_type: string; request_path: string; details?: Record<string, unknown> }): { title: string; description: string } {
  const action = log.action.charAt(0).toUpperCase() + log.action.slice(1);
  const resource = log.resource_type.charAt(0).toUpperCase() + log.resource_type.slice(1);
  const durationMs = log.details?.duration_ms;
  const durationStr = typeof durationMs === "number" ? ` (${durationMs.toFixed(0)}ms)` : "";
  return {
    title: `${action} ${resource}`,
    description: `${log.request_path}${durationStr}`,
  };
}

const activityIcons: Record<RecentActivity["type"], React.ReactNode> = {
  document_uploaded: <Upload className="h-4 w-4 text-blue-500" />,
  document_processed: <CheckCircle className="h-4 w-4 text-green-500" />,
  patient_added: <Users className="h-4 w-4 text-purple-500" />,
  job_completed: <Activity className="h-4 w-4 text-green-500" />,
  job_failed: <AlertCircle className="h-4 w-4 text-red-500" />,
};

export default function DashboardPage() {
  const { isDemo, isLoading: isAuthLoading } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dataMode, setDataMode] = useState<"live" | "simulation">("live");

  const refreshData = useCallback(async () => {
    if (isDemo) {
      setStats(DEMO_DASHBOARD_STATS);
      setRecentActivity(DEMO_RECENT_ACTIVITY);
      setDataMode("simulation");
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const [docsRes, patientsRes, trialsRes, auditRes] = await Promise.all([
        fetch("/api/documents?page=1&page_size=1").then(r => r.json()),
        fetch("/api/patients?page=1&page_size=1").then(r => r.json()),
        fetch("/api/trials").then(r => r.json()),
        fetch("/api/audit/logs?limit=10").then(r => r.json()),
      ]);

      // Count document statuses from a larger fetch
      const docsForStatus = await fetch("/api/documents?page=1&page_size=100").then(r => r.json());
      const docs = docsForStatus.documents || [];
      const completedDocs = docs.filter((d: { status: string }) => d.status === "completed").length;
      const processingDocs = docs.filter((d: { status: string }) => d.status === "processing" || d.status === "queued").length;
      const failedDocs = docs.filter((d: { status: string }) => d.status === "failed").length;

      const activeTrials = (trialsRes.trials || []).filter(
        (t: { status: string }) => t.status === "recruiting"
      ).length;

      setStats({
        totalDocuments: docsRes.total ?? 0,
        totalPatients: patientsRes.total ?? 0,
        activeTrials,
        completedDocs,
        processingDocs,
        failedDocs,
      });

      // Map audit logs to activity feed
      const logs = auditRes.logs || [];
      const activities: RecentActivity[] = logs.map(
        (log: { id: string; action: string; resource_type: string; request_path: string; timestamp: string; resource_id?: string; patient_id?: string; details?: Record<string, unknown> }, idx: number) => {
          const { title, description } = describeAuditLog(log);
          return {
            id: log.id || String(idx),
            type: mapAuditAction(log.action, log.resource_type),
            title,
            description,
            timestamp: formatTimeAgo(log.timestamp),
            patientId: log.patient_id || undefined,
            documentId: log.resource_type === "document" ? log.resource_id || undefined : undefined,
          };
        }
      );
      setRecentActivity(activities);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      setStats(DEMO_DASHBOARD_STATS);
      setRecentActivity(DEMO_RECENT_ACTIVITY);
      setDataMode("simulation");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthLoading) return;
    refreshData();
  }, [refreshData, isAuthLoading]);

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your clinical data processing system
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refreshData}
          disabled={isLoading}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {dataMode === "simulation" && (
        <DataSourceModeBanner
          mode={dataMode}
          title="Dashboard data source"
          description="Backend API is unavailable. Dashboard metrics and activity feed show demonstration data."
          backendEndpoints={["/api/documents", "/api/patients", "/api/trials", "/api/audit/logs"]}
        />
      )}

      {/* Persona Navigation (P3-002) */}
      <PersonaNavigator />

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Documents Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats ? stats.totalDocuments.toLocaleString() : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats ? `${stats.completedDocs} completed` : "Loading..."}
            </p>
          </CardContent>
        </Card>

        {/* Patients Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Patients</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats ? stats.totalPatients.toLocaleString() : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats ? "in knowledge graph" : "Loading..."}
            </p>
          </CardContent>
        </Card>

        {/* Active Trials Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Trials</CardTitle>
            <FlaskConical className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats ? stats.activeTrials : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats ? "currently recruiting" : "Loading..."}
            </p>
          </CardContent>
        </Card>

        {/* Success Rate Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats
                ? stats.completedDocs + stats.failedDocs > 0
                  ? `${Math.round((stats.completedDocs / (stats.completedDocs + stats.failedDocs)) * 100)}%`
                  : "100%"
                : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats ? `${stats.failedDocs} failed` : "Loading..."}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Activity */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>
              Latest updates from the clinical data pipeline
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentActivity.map((activity) => (
                <div
                  key={activity.id}
                  className="flex items-start gap-4 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="mt-0.5">{activityIcons[activity.type]}</div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">{activity.title}</p>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {activity.timestamp}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {activity.description}
                    </p>
                    {(activity.documentId || activity.patientId) && (
                      <div className="flex gap-2 pt-1">
                        {activity.documentId && (
                          <Link href={`/documents/${activity.documentId}`}>
                            <Badge variant="secondary" className="text-xs">
                              View Document
                            </Badge>
                          </Link>
                        )}
                        {activity.patientId && (
                          <Link href={`/patients/${activity.patientId}/graph`}>
                            <Badge variant="secondary" className="text-xs">
                              View Patient
                            </Badge>
                          </Link>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4">
              <Button variant="ghost" size="sm" className="w-full">
                View all activity
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks and shortcuts</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link href="/documents/upload" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Upload className="mr-2 h-4 w-4" />
                Upload Document
              </Button>
            </Link>
            <Link href="/search" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Search className="mr-2 h-4 w-4" />
                Search Clinical Data
              </Button>
            </Link>
            <Link href="/patients" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Users className="mr-2 h-4 w-4" />
                View Patients
              </Button>
            </Link>
            <Link href="/documents" className="block">
              <Button variant="outline" className="w-full justify-start">
                <FileText className="mr-2 h-4 w-4" />
                Browse Documents
              </Button>
            </Link>
            <Link href="/quality" className="block">
              <Button variant="outline" className="w-full justify-start">
                <BarChart3 className="mr-2 h-4 w-4" />
                Quality Metrics
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
          <CardDescription>
            Current status of processing pipelines and services
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-sm font-medium">NLP Pipeline</p>
                <p className="text-xs text-muted-foreground">Operational</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-sm font-medium">OMOP Mapper</p>
                <p className="text-xs text-muted-foreground">Operational</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-sm font-medium">Database</p>
                <p className="text-xs text-muted-foreground">Connected</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-yellow-100 dark:bg-yellow-900">
                <Clock className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
              </div>
              <div>
                <p className="text-sm font-medium">Job Queue</p>
                <p className="text-xs text-muted-foreground">
                  {stats?.processingDocs ?? 0} pending
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
