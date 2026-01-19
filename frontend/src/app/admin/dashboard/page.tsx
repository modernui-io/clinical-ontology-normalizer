"use client";

import { useState, useEffect } from "react";
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
  LayoutDashboard,
  Server,
  Database,
  HardDrive,
  Activity,
  Users,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Trash2,
  RotateCcw,
  Cpu,
  MemoryStick,
  Wifi,
  WifiOff,
  Clock,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Zap,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";

// Types
interface SystemService {
  name: string;
  status: "healthy" | "degraded" | "down";
  responseTime: number;
  uptime: string;
  lastChecked: string;
}

interface SystemMetrics {
  cpuUsage: number;
  memoryUsage: number;
  diskUsage: number;
  activeConnections: number;
}

interface RequestVolumeData {
  time: string;
  requests: number;
  errors: number;
}

interface RecentError {
  id: string;
  timestamp: string;
  service: string;
  message: string;
  statusCode: number;
  count: number;
}

// Mock Data
const mockServices: SystemService[] = [
  {
    name: "API Server",
    status: "healthy",
    responseTime: 45,
    uptime: "99.99%",
    lastChecked: "2026-01-19T14:45:00Z",
  },
  {
    name: "PostgreSQL",
    status: "healthy",
    responseTime: 12,
    uptime: "99.98%",
    lastChecked: "2026-01-19T14:45:00Z",
  },
  {
    name: "Redis Cache",
    status: "healthy",
    responseTime: 2,
    uptime: "99.99%",
    lastChecked: "2026-01-19T14:45:00Z",
  },
  {
    name: "Kafka",
    status: "degraded",
    responseTime: 156,
    uptime: "98.75%",
    lastChecked: "2026-01-19T14:45:00Z",
  },
  {
    name: "Neo4j Graph DB",
    status: "healthy",
    responseTime: 28,
    uptime: "99.95%",
    lastChecked: "2026-01-19T14:45:00Z",
  },
];

const mockMetrics: SystemMetrics = {
  cpuUsage: 42,
  memoryUsage: 68,
  diskUsage: 54,
  activeConnections: 127,
};

const generateRequestVolumeData = (): RequestVolumeData[] => {
  const data: RequestVolumeData[] = [];
  const now = new Date();
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60 * 60 * 1000);
    const hour = time.getHours();
    // Simulate more traffic during business hours
    const baseRequests = hour >= 8 && hour <= 18 ? 1500 : 300;
    const requests = Math.floor(baseRequests + Math.random() * 500);
    const errors = Math.floor(requests * (Math.random() * 0.02)); // 0-2% error rate
    data.push({
      time: time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      requests,
      errors,
    });
  }
  return data;
};

const mockRequestVolume = generateRequestVolumeData();

const mockRecentErrors: RecentError[] = [
  {
    id: "err-001",
    timestamp: "2026-01-19T14:42:15Z",
    service: "API Server",
    message: "Connection timeout to external FHIR server",
    statusCode: 504,
    count: 3,
  },
  {
    id: "err-002",
    timestamp: "2026-01-19T14:38:22Z",
    service: "Kafka",
    message: "Consumer lag threshold exceeded",
    statusCode: 500,
    count: 12,
  },
  {
    id: "err-003",
    timestamp: "2026-01-19T14:25:10Z",
    service: "API Server",
    message: "Invalid request body - missing required field 'patient_id'",
    statusCode: 400,
    count: 5,
  },
  {
    id: "err-004",
    timestamp: "2026-01-19T14:15:45Z",
    service: "PostgreSQL",
    message: "Query timeout exceeded for complex join operation",
    statusCode: 500,
    count: 2,
  },
  {
    id: "err-005",
    timestamp: "2026-01-19T13:58:30Z",
    service: "API Server",
    message: "Rate limit exceeded for IP 192.168.1.105",
    statusCode: 429,
    count: 8,
  },
];

// Helper functions
const getStatusIcon = (status: string) => {
  switch (status) {
    case "healthy":
      return <CheckCircle className="h-5 w-5 text-green-600" />;
    case "degraded":
      return <AlertTriangle className="h-5 w-5 text-amber-500" />;
    case "down":
      return <XCircle className="h-5 w-5 text-red-600" />;
    default:
      return <WifiOff className="h-5 w-5 text-gray-400" />;
  }
};

const getStatusColor = (status: string): string => {
  switch (status) {
    case "healthy":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "degraded":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "down":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getServiceIcon = (name: string) => {
  switch (name) {
    case "API Server":
      return <Server className="h-4 w-4" />;
    case "PostgreSQL":
      return <Database className="h-4 w-4" />;
    case "Redis Cache":
      return <Zap className="h-4 w-4" />;
    case "Kafka":
      return <Activity className="h-4 w-4" />;
    case "Neo4j Graph DB":
      return <HardDrive className="h-4 w-4" />;
    default:
      return <Server className="h-4 w-4" />;
  }
};

const formatTimestamp = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

const formatTimeAgo = (timestamp: string): string => {
  const now = new Date();
  const date = new Date(timestamp);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

const getProgressColor = (value: number): string => {
  if (value < 50) return "bg-green-500";
  if (value < 75) return "bg-amber-500";
  return "bg-red-500";
};

export default function AdminDashboardPage() {
  const [services, setServices] = useState<SystemService[]>(mockServices);
  const [metrics, setMetrics] = useState<SystemMetrics>(mockMetrics);
  const [requestVolume] = useState<RequestVolumeData[]>(mockRequestVolume);
  const [recentErrors] = useState<RecentError[]>(mockRecentErrors);
  const [isLoading, setIsLoading] = useState(false);
  const [activeUsers] = useState(42);
  const [isClearing, setIsClearing] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      // Update metrics with small random variations
      setMetrics((prev) => ({
        cpuUsage: Math.max(0, Math.min(100, prev.cpuUsage + (Math.random() - 0.5) * 5)),
        memoryUsage: Math.max(0, Math.min(100, prev.memoryUsage + (Math.random() - 0.5) * 2)),
        diskUsage: prev.diskUsage, // Disk usage stays relatively stable
        activeConnections: Math.max(0, prev.activeConnections + Math.floor((Math.random() - 0.5) * 10)),
      }));
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const refreshData = async () => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setServices(mockServices);
    setMetrics(mockMetrics);
    setIsLoading(false);
  };

  const handleClearCache = async () => {
    setIsClearing(true);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsClearing(false);
    // In production, this would call an API endpoint
    console.log("Cache cleared (mock)");
  };

  const handleRestartServices = async () => {
    setIsRestarting(true);
    await new Promise((resolve) => setTimeout(resolve, 3000));
    setIsRestarting(false);
    // In production, this would call an API endpoint
    console.log("Services restarted (mock)");
  };

  const totalRequests = requestVolume.reduce((sum, d) => sum + d.requests, 0);
  const totalErrors = requestVolume.reduce((sum, d) => sum + d.errors, 0);
  const errorRate = ((totalErrors / totalRequests) * 100).toFixed(2);
  const healthyServices = services.filter((s) => s.status === "healthy").length;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <LayoutDashboard className="h-6 w-6" />
            Admin Dashboard
          </h1>
          <p className="text-muted-foreground">
            System health monitoring and administration
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {/* System Health Status Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {services.map((service) => (
          <Card key={service.name}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                {getServiceIcon(service.name)}
                {service.name}
              </CardTitle>
              {getStatusIcon(service.status)}
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <Badge className={getStatusColor(service.status)}>
                  {service.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {service.responseTime}ms
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Uptime: {service.uptime}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Key Metrics Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Requests (24h)</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalRequests.toLocaleString()}</div>
            <div className="flex items-center text-xs text-muted-foreground">
              <TrendingUp className="h-3 w-3 mr-1 text-green-600" />
              <span className="text-green-600">+12%</span>
              <span className="ml-1">from yesterday</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Error Rate</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{errorRate}%</div>
            <div className="flex items-center text-xs text-muted-foreground">
              <TrendingDown className="h-3 w-3 mr-1 text-green-600" />
              <span className="text-green-600">-0.3%</span>
              <span className="ml-1">from yesterday</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Users</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeUsers}</div>
            <p className="text-xs text-muted-foreground">Currently online</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {healthyServices}/{services.length}
            </div>
            <p className="text-xs text-muted-foreground">Services healthy</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts and Gauges Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Request Volume Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Request Volume (Last 24 Hours)</CardTitle>
            <CardDescription>
              API requests and error counts over time
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={requestVolume}>
                  <defs>
                    <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorErrors" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--popover))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "6px",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="requests"
                    stroke="#3b82f6"
                    fill="url(#colorRequests)"
                    strokeWidth={2}
                    name="Requests"
                  />
                  <Area
                    type="monotone"
                    dataKey="errors"
                    stroke="#ef4444"
                    fill="url(#colorErrors)"
                    strokeWidth={2}
                    name="Errors"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* CPU/Memory Gauges */}
        <Card>
          <CardHeader>
            <CardTitle>System Resources</CardTitle>
            <CardDescription>Current resource utilization</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">CPU Usage</span>
                </div>
                <span className="text-sm font-bold">{Math.round(metrics.cpuUsage)}%</span>
              </div>
              <div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={`h-full transition-all duration-500 ${getProgressColor(metrics.cpuUsage)}`}
                  style={{ width: `${metrics.cpuUsage}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MemoryStick className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Memory Usage</span>
                </div>
                <span className="text-sm font-bold">{Math.round(metrics.memoryUsage)}%</span>
              </div>
              <div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={`h-full transition-all duration-500 ${getProgressColor(metrics.memoryUsage)}`}
                  style={{ width: `${metrics.memoryUsage}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <HardDrive className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Disk Usage</span>
                </div>
                <span className="text-sm font-bold">{Math.round(metrics.diskUsage)}%</span>
              </div>
              <div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={`h-full transition-all duration-500 ${getProgressColor(metrics.diskUsage)}`}
                  style={{ width: `${metrics.diskUsage}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Wifi className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Active Connections</span>
                </div>
                <span className="text-sm font-bold">{metrics.activeConnections}</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Max capacity: 500 connections
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Errors and Quick Actions */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Errors Table */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent Errors</CardTitle>
            <CardDescription>
              Latest system errors and warnings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Service</TableHead>
                  <TableHead>Message</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentErrors.map((error) => (
                  <TableRow key={error.id}>
                    <TableCell className="text-sm">
                      <div>
                        <div className="font-medium">{formatTimestamp(error.timestamp)}</div>
                        <div className="text-xs text-muted-foreground">
                          {formatTimeAgo(error.timestamp)}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{error.service}</Badge>
                    </TableCell>
                    <TableCell className="max-w-[300px]">
                      <p className="text-sm truncate" title={error.message}>
                        {error.message}
                      </p>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          error.statusCode >= 500
                            ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                            : error.statusCode >= 400
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
                            : "bg-gray-100 text-gray-800"
                        }
                      >
                        {error.statusCode}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm font-medium">
                      {error.count}x
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Administrative operations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={handleClearCache}
              disabled={isClearing}
            >
              <Trash2 className={`mr-2 h-4 w-4 ${isClearing ? "animate-pulse" : ""}`} />
              {isClearing ? "Clearing Cache..." : "Clear All Caches"}
            </Button>

            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={handleRestartServices}
              disabled={isRestarting}
            >
              <RotateCcw className={`mr-2 h-4 w-4 ${isRestarting ? "animate-spin" : ""}`} />
              {isRestarting ? "Restarting Services..." : "Restart Services"}
            </Button>

            <Button variant="outline" className="w-full justify-start">
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh Health Checks
            </Button>

            <Button variant="outline" className="w-full justify-start">
              <Activity className="mr-2 h-4 w-4" />
              View Full Metrics
            </Button>

            <div className="pt-4 border-t">
              <p className="text-xs text-muted-foreground mb-2">
                Last health check: {formatTimeAgo(services[0].lastChecked)}
              </p>
              <p className="text-xs text-muted-foreground flex items-center">
                <Clock className="h-3 w-3 mr-1" />
                Next scheduled check in 5 minutes
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
