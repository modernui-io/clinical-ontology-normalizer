"use client";

import { useState, useEffect } from "react";
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
} from "lucide-react";

// Mock data - In production, this would come from the API
interface DashboardStats {
  totalDocuments: number;
  documentsThisWeek: number;
  totalPatients: number;
  patientsThisWeek: number;
  processingJobs: number;
  completedJobs: number;
  failedJobs: number;
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

const mockStats: DashboardStats = {
  totalDocuments: 1247,
  documentsThisWeek: 89,
  totalPatients: 342,
  patientsThisWeek: 12,
  processingJobs: 3,
  completedJobs: 156,
  failedJobs: 2,
};

const mockRecentActivity: RecentActivity[] = [
  {
    id: "1",
    type: "document_processed",
    title: "Discharge Summary Processed",
    description: "Patient John Smith - 15 clinical facts extracted",
    timestamp: "5 minutes ago",
    patientId: "P001",
    documentId: "D001",
  },
  {
    id: "2",
    type: "document_uploaded",
    title: "Progress Note Uploaded",
    description: "Patient Mary Johnson - Queued for processing",
    timestamp: "12 minutes ago",
    patientId: "P002",
    documentId: "D002",
  },
  {
    id: "3",
    type: "job_completed",
    title: "NLP Pipeline Completed",
    description: "Batch processing of 5 documents finished",
    timestamp: "25 minutes ago",
  },
  {
    id: "4",
    type: "patient_added",
    title: "New Patient Added",
    description: "Robert Williams added to the system",
    timestamp: "1 hour ago",
    patientId: "P003",
  },
  {
    id: "5",
    type: "job_failed",
    title: "Processing Failed",
    description: "Document D103 - Invalid format detected",
    timestamp: "2 hours ago",
    documentId: "D103",
  },
];

const activityIcons: Record<RecentActivity["type"], React.ReactNode> = {
  document_uploaded: <Upload className="h-4 w-4 text-blue-500" />,
  document_processed: <CheckCircle className="h-4 w-4 text-green-500" />,
  patient_added: <Users className="h-4 w-4 text-purple-500" />,
  job_completed: <Activity className="h-4 w-4 text-green-500" />,
  job_failed: <AlertCircle className="h-4 w-4 text-red-500" />,
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>(mockStats);
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>(mockRecentActivity);
  const [isLoading, setIsLoading] = useState(false);

  const refreshData = async () => {
    setIsLoading(true);
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setStats(mockStats);
    setRecentActivity(mockRecentActivity);
    setIsLoading(false);
  };

  useEffect(() => {
    // In production, fetch real data from API
    // refreshData();
  }, []);

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

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Documents Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Documents</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalDocuments.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600 dark:text-green-400">
                +{stats.documentsThisWeek}
              </span>{" "}
              this week
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
            <div className="text-2xl font-bold">{stats.totalPatients.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600 dark:text-green-400">
                +{stats.patientsThisWeek}
              </span>{" "}
              new patients
            </p>
          </CardContent>
        </Card>

        {/* Processing Jobs Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Processing Jobs</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.processingJobs}</div>
            <p className="text-xs text-muted-foreground">
              {stats.completedJobs} completed today
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
              {stats.completedJobs + stats.failedJobs > 0
                ? Math.round(
                    (stats.completedJobs / (stats.completedJobs + stats.failedJobs)) * 100
                  )
                : 100}
              %
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.failedJobs} failed jobs
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
                  {stats.processingJobs} pending
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
