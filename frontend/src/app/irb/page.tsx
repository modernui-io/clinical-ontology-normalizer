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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Scale,
  FileCheck,
  Users,
  RefreshCw,
  Loader2,
  AlertCircle,
  Building2,
  Calendar,
  Mail,
  CheckCircle2,
  Clock,
  XCircle,
  FileText,
} from "lucide-react";

// Types
interface IRBBoard {
  id: string;
  name: string;
  board_type: string;
  organization: string;
  country: string;
  contact_email: string;
  meeting_schedule: string;
  status: string;
}

interface IRBSubmission {
  id: string;
  board_id: string;
  trial_id: string;
  submission_type: string;
  submission_number: string;
  protocol_version: string;
  submitted_date: string;
  status: string;
  decision_date?: string;
  approval_expiry?: string;
  assigned_reviewer?: string;
}

interface IRBData {
  boards: {
    items: IRBBoard[];
    total: number;
  };
  submissions: {
    items: IRBSubmission[];
    total: number;
  };
}

// Helper functions
const getSubmissionTypeBadge = (type: string) => {
  const colors: Record<string, string> = {
    initial: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    amendment: "bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
    continuing_review: "bg-yellow-50 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300",
    safety_report: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  };
  return colors[type] || "bg-gray-50 text-gray-700 dark:bg-gray-950 dark:text-gray-300";
};

const getStatusBadge = (status: string) => {
  const colors: Record<string, string> = {
    submitted: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    under_review: "bg-yellow-50 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300",
    approved: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300",
    rejected: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  };
  return colors[status] || "bg-gray-50 text-gray-700 dark:bg-gray-950 dark:text-gray-300";
};

const getStatusIcon = (status: string) => {
  const icons: Record<string, React.ReactNode> = {
    submitted: <Clock className="h-3.5 w-3.5" />,
    under_review: <RefreshCw className="h-3.5 w-3.5" />,
    approved: <CheckCircle2 className="h-3.5 w-3.5" />,
    rejected: <XCircle className="h-3.5 w-3.5" />,
  };
  return icons[status] || <FileText className="h-3.5 w-3.5" />;
};

const formatDate = (dateString?: string): string => {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const formatSubmissionType = (type: string): string => {
  return type
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

const formatStatus = (status: string): string => {
  return status
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

export default function IRBPage() {
  const [data, setData] = useState<IRBData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [boardsRes, submissionsRes] = await Promise.all([
        fetch("/api/central-irb/boards"),
        fetch("/api/central-irb/submissions"),
      ]);

      if (!boardsRes.ok || !submissionsRes.ok) {
        throw new Error("Failed to fetch IRB data");
      }

      const [boardsData, submissionsData] = await Promise.all([
        boardsRes.json(),
        submissionsRes.json(),
      ]);

      setData({
        boards: boardsData,
        submissions: submissionsData,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Calculate summary stats
  const stats = data
    ? {
        activeBoards: data.boards.items.filter((b) => b.status === "active").length,
        totalSubmissions: data.submissions.total,
        approvedCount: data.submissions.items.filter((s) => s.status === "approved").length,
        pendingReviewCount: data.submissions.items.filter(
          (s) => s.status === "submitted" || s.status === "under_review"
        ).length,
      }
    : { activeBoards: 0, totalSubmissions: 0, approvedCount: 0, pendingReviewCount: 0 };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">IRB/DSMB Management</h1>
          <p className="text-muted-foreground">
            Central IRB boards, submissions, and regulatory oversight
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchData}
          disabled={isLoading}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {isLoading && !data ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Key Metrics Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card className="border-l-4 border-l-blue-500">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Active Boards</CardTitle>
                <Scale className="h-4 w-4 text-blue-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">{stats.activeBoards}</div>
                <p className="text-xs text-muted-foreground">
                  IRB boards currently active
                </p>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-purple-500">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Total Submissions</CardTitle>
                <FileCheck className="h-4 w-4 text-purple-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-purple-600">
                  {stats.totalSubmissions}
                </div>
                <p className="text-xs text-muted-foreground">
                  Across all protocols
                </p>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-green-500">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Approved</CardTitle>
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">
                  {stats.approvedCount}
                </div>
                <p className="text-xs text-muted-foreground">
                  Successfully approved submissions
                </p>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-yellow-500">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
                <Users className="h-4 w-4 text-yellow-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-yellow-600">
                  {stats.pendingReviewCount}
                </div>
                <p className="text-xs text-muted-foreground">
                  Awaiting decision
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Main Content Tabs */}
          <Tabs defaultValue="boards" className="space-y-4">
            <TabsList>
              <TabsTrigger value="boards" className="gap-2">
                <Scale className="h-4 w-4" />
                IRB Boards
              </TabsTrigger>
              <TabsTrigger value="submissions" className="gap-2">
                <FileCheck className="h-4 w-4" />
                Submissions
              </TabsTrigger>
            </TabsList>

            {/* IRB Boards Tab */}
            <TabsContent value="boards" className="space-y-4">
              {data?.boards.items.map((board) => (
                <Card key={board.id} className="transition-colors hover:bg-muted/50">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <CardTitle className="text-lg">{board.name}</CardTitle>
                          <Badge
                            variant={board.status === "active" ? "default" : "secondary"}
                            className={
                              board.status === "active"
                                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                                : ""
                            }
                          >
                            {formatStatus(board.status)}
                          </Badge>
                        </div>
                        <CardDescription>{board.id}</CardDescription>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {formatSubmissionType(board.board_type)}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                      <div className="flex items-start gap-3">
                        <div className="rounded-lg bg-muted p-2">
                          <Building2 className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="space-y-0.5">
                          <p className="text-xs text-muted-foreground">Organization</p>
                          <p className="text-sm font-medium">{board.organization}</p>
                          <p className="text-xs text-muted-foreground">{board.country}</p>
                        </div>
                      </div>

                      <div className="flex items-start gap-3">
                        <div className="rounded-lg bg-muted p-2">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="space-y-0.5">
                          <p className="text-xs text-muted-foreground">Meeting Schedule</p>
                          <p className="text-sm font-medium">{board.meeting_schedule}</p>
                        </div>
                      </div>

                      <div className="flex items-start gap-3">
                        <div className="rounded-lg bg-muted p-2">
                          <Mail className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="space-y-0.5">
                          <p className="text-xs text-muted-foreground">Contact</p>
                          <p className="text-sm font-medium break-all">{board.contact_email}</p>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}

              {data && data.boards.items.length === 0 && (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-12">
                    <Scale className="h-12 w-12 text-muted-foreground/50" />
                    <p className="mt-4 text-sm text-muted-foreground">
                      No IRB boards found
                    </p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Submissions Tab */}
            <TabsContent value="submissions" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>IRB Submissions</CardTitle>
                  <CardDescription>
                    Protocol submissions across all IRB boards
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Submission #</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Protocol Version</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Submitted</TableHead>
                          <TableHead>Decision Date</TableHead>
                          <TableHead>Expiry</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data && data.submissions.items.length > 0 ? (
                          data.submissions.items.map((submission) => (
                            <TableRow key={submission.id}>
                              <TableCell>
                                <div className="flex flex-col gap-1">
                                  <code className="text-xs font-mono">
                                    {submission.submission_number}
                                  </code>
                                  <span className="text-xs text-muted-foreground">
                                    {submission.id}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge
                                  variant="outline"
                                  className={getSubmissionTypeBadge(submission.submission_type)}
                                >
                                  {formatSubmissionType(submission.submission_type)}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <code className="text-sm">{submission.protocol_version}</code>
                              </TableCell>
                              <TableCell>
                                <Badge
                                  variant="outline"
                                  className={`flex items-center gap-1.5 w-fit ${getStatusBadge(
                                    submission.status
                                  )}`}
                                >
                                  {getStatusIcon(submission.status)}
                                  {formatStatus(submission.status)}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-sm">
                                {formatDate(submission.submitted_date)}
                              </TableCell>
                              <TableCell className="text-sm">
                                {formatDate(submission.decision_date)}
                              </TableCell>
                              <TableCell className="text-sm">
                                {formatDate(submission.approval_expiry)}
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell colSpan={7} className="h-32 text-center">
                              <div className="flex flex-col items-center justify-center text-muted-foreground">
                                <FileCheck className="h-8 w-8 mb-2 opacity-50" />
                                <p className="text-sm">No submissions found</p>
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
