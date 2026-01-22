"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Clock,
  ExternalLink,
  Info,
  Loader2,
  Play,
  RefreshCw,
  Settings,
  Shield,
  Stethoscope,
  XCircle,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface CDSService {
  hook: string;
  title: string;
  description: string;
  id: string;
  prefetch?: Record<string, string>;
}

interface CDSHookLog {
  hook_id: string;
  hook_type: string;
  timestamp: string;
  patient_id: string | null;
  user_id: string | null;
  cards_returned: number;
  duration_ms: number;
  error: string | null;
}

interface CDSStats {
  services_count: number;
  total_invocations: number;
  recent_invocations_24h: number;
  invocations_by_hook: Record<string, number>;
}

// =============================================================================
// Hook Icons
// =============================================================================

const HOOK_ICONS: Record<string, React.ReactNode> = {
  "patient-view": <Stethoscope className="h-5 w-5" />,
  "order-select": <Activity className="h-5 w-5" />,
  "order-sign": <Shield className="h-5 w-5" />,
  "medication-prescribe": <AlertCircle className="h-5 w-5" />,
};

const HOOK_COLORS: Record<string, string> = {
  "patient-view": "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  "order-select": "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  "order-sign": "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  "medication-prescribe": "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
};

// =============================================================================
// API Functions
// =============================================================================

async function fetchServices(): Promise<CDSService[]> {
  const response = await fetch("/api/cds-services");
  if (!response.ok) throw new Error("Failed to fetch CDS services");
  const data = await response.json();
  return data.services;
}

async function fetchStats(): Promise<CDSStats> {
  const response = await fetch("/api/cds-services/admin/stats");
  if (!response.ok) throw new Error("Failed to fetch CDS stats");
  return response.json();
}

async function fetchLogs(limit: number = 10): Promise<CDSHookLog[]> {
  const response = await fetch(`/api/cds-services/admin/logs?limit=${limit}`);
  if (!response.ok) throw new Error("Failed to fetch CDS logs");
  const data = await response.json();
  return data.logs;
}

// =============================================================================
// Service Card Component
// =============================================================================

interface ServiceCardProps {
  service: CDSService;
  invocationCount: number;
}

function ServiceCard({ service, invocationCount }: ServiceCardProps) {
  const icon = HOOK_ICONS[service.hook] || <Activity className="h-5 w-5" />;
  const colorClass = HOOK_COLORS[service.hook] || "bg-gray-100 text-gray-700";

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className={`rounded-lg p-2 ${colorClass}`}>{icon}</div>
          <Badge variant="outline" className="text-xs">
            {invocationCount} invocations
          </Badge>
        </div>
        <CardTitle className="text-lg mt-3">{service.title}</CardTitle>
        <CardDescription className="text-sm">{service.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono bg-muted px-2 py-1 rounded text-xs">
              {service.hook}
            </span>
            <span className="text-muted-foreground/50">|</span>
            <span className="font-mono text-xs">{service.id}</span>
          </div>

          {service.prefetch && Object.keys(service.prefetch).length > 0 && (
            <div className="text-xs text-muted-foreground">
              <span className="font-medium">Prefetch:</span>{" "}
              {Object.keys(service.prefetch).join(", ")}
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <Link href={`/cds/test?hook=${service.hook}`}>
              <Button size="sm" variant="outline">
                <Play className="h-3 w-3 mr-1" />
                Test
              </Button>
            </Link>
            <Button size="sm" variant="ghost">
              <Settings className="h-3 w-3 mr-1" />
              Configure
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Log Entry Component
// =============================================================================

interface LogEntryProps {
  log: CDSHookLog;
}

function LogEntry({ log }: LogEntryProps) {
  const isError = !!log.error;
  const hasCards = log.cards_returned > 0;

  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-2">
          {isError ? (
            <XCircle className="h-4 w-4 text-red-500" />
          ) : hasCards ? (
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
          ) : (
            <CheckCircle className="h-4 w-4 text-green-500" />
          )}
          <span className="font-mono text-sm">{log.hook_type}</span>
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {log.patient_id || "-"}
        </span>
      </TableCell>
      <TableCell>
        <Badge variant={hasCards ? "default" : "secondary"}>
          {log.cards_returned} cards
        </Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {log.duration_ms.toFixed(1)}ms
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">
          {new Date(log.timestamp).toLocaleString()}
        </span>
      </TableCell>
      <TableCell>
        {isError && (
          <span className="text-xs text-red-500 truncate max-w-[200px] block">
            {log.error}
          </span>
        )}
      </TableCell>
    </TableRow>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function CDSPage() {
  const [services, setServices] = useState<CDSService[]>([]);
  const [stats, setStats] = useState<CDSStats | null>(null);
  const [logs, setLogs] = useState<CDSHookLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [servicesData, statsData, logsData] = await Promise.all([
        fetchServices(),
        fetchStats(),
        fetchLogs(10),
      ]);
      setServices(servicesData);
      setStats(statsData);
      setLogs(logsData);
    } catch (error) {
      console.error("Failed to load CDS data:", error);
      toast.error("Failed to load CDS data");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">CDS Hooks</h1>
          <p className="text-muted-foreground">
            Clinical Decision Support services and monitoring
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Link href="/cds/test">
            <Button size="sm">
              <Play className="mr-2 h-4 w-4" />
              Test Hook
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Services</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.services_count || 0}</div>
            <p className="text-xs text-muted-foreground">CDS hooks available</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Invocations</CardTitle>
            <Stethoscope className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.total_invocations.toLocaleString() || 0}
            </div>
            <p className="text-xs text-muted-foreground">All time</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Last 24 Hours</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.recent_invocations_24h.toLocaleString() || 0}
            </div>
            <p className="text-xs text-muted-foreground">Recent invocations</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Alerts Generated</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {logs.reduce((sum, log) => sum + log.cards_returned, 0)}
            </div>
            <p className="text-xs text-muted-foreground">From recent logs</p>
          </CardContent>
        </Card>
      </div>

      {/* Services Grid */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Available Services</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {services.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              invocationCount={stats?.invocations_by_hook[service.hook] || 0}
            />
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>Latest CDS hook invocations</CardDescription>
            </div>
            <Link href="/cds/test">
              <Button variant="ghost" size="sm">
                View All
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {logs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Info className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No recent hook invocations</p>
              <Link href="/cds/test" className="mt-2 inline-block">
                <Button variant="outline" size="sm">
                  Test a hook
                </Button>
              </Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Hook</TableHead>
                  <TableHead>Patient</TableHead>
                  <TableHead>Cards</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <LogEntry key={log.hook_id} log={log} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Documentation Link */}
      <Card className="bg-muted/50">
        <CardContent className="flex items-center justify-between py-4">
          <div className="flex items-center gap-3">
            <div className="bg-primary/10 p-2 rounded-lg">
              <ExternalLink className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="font-medium">CDS Hooks Specification</p>
              <p className="text-sm text-muted-foreground">
                Learn more about the CDS Hooks standard
              </p>
            </div>
          </div>
          <a
            href="https://cds-hooks.org/"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button variant="outline" size="sm">
              View Docs
              <ExternalLink className="ml-2 h-3 w-3" />
            </Button>
          </a>
        </CardContent>
      </Card>
    </div>
  );
}
