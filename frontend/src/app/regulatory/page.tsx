"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  FileCheck,
  Clock,
  AlertTriangle,
  Send,
  RefreshCw,
  Search,
  Loader2,
  AlertCircle,
  ExternalLink,
  Building2,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface RegulatorySubmission {
  id: string;
  title: string;
  submission_type: string;
  regulatory_body: string;
  trial_id: string;
  status: string;
  reference_number: string;
  submitted_date: string | null;
  expected_response_date: string | null;
  actual_response_date: string | null;
  assigned_to: string;
  reviewer: string;
  priority: string;
  documents: unknown[];
  notes: string;
}

interface SubmissionsResponse {
  items: RegulatorySubmission[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================================================
// Helpers
// ============================================================================

function getStatusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    DRAFT: {
      className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
      label: "Draft",
    },
    SUBMITTED: {
      className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      label: "Submitted",
    },
    UNDER_REVIEW: {
      className: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
      label: "Under Review",
    },
    APPROVED: {
      className: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
      label: "Approved",
    },
    REJECTED: {
      className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
      label: "Rejected",
    },
    WITHDRAWN: {
      className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
      label: "Withdrawn",
    },
  };
  const entry = map[status] ?? {
    className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    label: status,
  };
  return <Badge className={entry.className}>{entry.label}</Badge>;
}

function getPriorityBadge(priority: string) {
  const map: Record<string, { className: string; label: string }> = {
    LOW: {
      className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
      label: "Low",
    },
    STANDARD: {
      className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      label: "Standard",
    },
    HIGH: {
      className: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
      label: "High",
    },
    URGENT: {
      className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
      label: "Urgent",
    },
    CRITICAL: {
      className: "bg-red-600 text-white",
      label: "Critical",
    },
  };
  const entry = map[priority] ?? {
    className: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    label: priority,
  };
  return <Badge className={entry.className}>{entry.label}</Badge>;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function isOverdue(submission: RegulatorySubmission): boolean {
  if (!submission.expected_response_date || submission.actual_response_date) return false;
  return new Date(submission.expected_response_date) < new Date();
}

function isAwaitingResponse(submission: RegulatorySubmission): boolean {
  return (
    submission.status === "SUBMITTED" ||
    submission.status === "UNDER_REVIEW"
  ) && !submission.actual_response_date;
}

// ============================================================================
// Main Component
// ============================================================================

export default function RegulatorySubmissionsPage() {
  const [submissions, setSubmissions] = useState<RegulatorySubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("all");

  const loadSubmissions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/regulatory-submissions/submissions");
      if (!response.ok) throw new Error("Failed to fetch regulatory submissions");
      const data: SubmissionsResponse = await response.json();
      setSubmissions(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load submissions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSubmissions();
  }, [loadSubmissions]);

  // Derived counts
  const totalCount = submissions.length;
  const pendingCount = submissions.filter(isAwaitingResponse).length;
  const approvedCount = submissions.filter((s) => s.status === "APPROVED").length;
  const overdueCount = submissions.filter(isOverdue).length;

  // Filtered submissions
  const filteredSubmissions = submissions.filter((s) => {
    const matchesSearch =
      searchQuery === "" ||
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.reference_number.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;

    switch (activeTab) {
      case "pending":
        return isAwaitingResponse(s);
      case "approved":
        return s.status === "APPROVED";
      case "overdue":
        return isOverdue(s);
      default:
        return true;
    }
  });

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Regulatory Submissions</h1>
          <p className="text-muted-foreground">
            Track and manage regulatory filings across agencies
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadSubmissions} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <span className="text-red-700 dark:text-red-300">{error}</span>
            <Button variant="outline" size="sm" onClick={loadSubmissions} className="ml-auto">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {loading && submissions.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Total Submissions</CardTitle>
                <FileCheck className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{totalCount}</div>
                <p className="text-xs text-muted-foreground">
                  All regulatory submissions
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Pending Response</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{pendingCount}</div>
                <p className="text-xs text-muted-foreground">
                  Awaiting agency response
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Approved</CardTitle>
                <Send className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{approvedCount}</div>
                <p className="text-xs text-muted-foreground">
                  Successfully approved
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Overdue</CardTitle>
                <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${overdueCount > 0 ? "text-red-600" : ""}`}>
                  {overdueCount}
                </div>
                <p className="text-xs text-muted-foreground">
                  Past expected response date
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Tabs + Search */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <TabsList>
                <TabsTrigger value="all">All ({totalCount})</TabsTrigger>
                <TabsTrigger value="pending">Pending ({pendingCount})</TabsTrigger>
                <TabsTrigger value="approved">Approved ({approvedCount})</TabsTrigger>
                <TabsTrigger value="overdue">Overdue ({overdueCount})</TabsTrigger>
              </TabsList>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by title or reference..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 w-[280px]"
                />
              </div>
            </div>

            {/* Shared content for all tabs */}
            {["all", "pending", "approved", "overdue"].map((tab) => (
              <TabsContent key={tab} value={tab} className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Building2 className="h-5 w-5" />
                      Submissions
                    </CardTitle>
                    <CardDescription>
                      {filteredSubmissions.length} submission{filteredSubmissions.length !== 1 ? "s" : ""} found
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {filteredSubmissions.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <FileCheck className="h-12 w-12 mb-3" />
                        <p className="text-sm">No submissions match the current filter</p>
                      </div>
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Reference #</TableHead>
                            <TableHead>Title</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Regulatory Body</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Priority</TableHead>
                            <TableHead>Assigned To</TableHead>
                            <TableHead>Submitted Date</TableHead>
                            <TableHead>Response Due</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filteredSubmissions.map((submission) => (
                            <TableRow key={submission.id}>
                              <TableCell className="font-mono text-sm">
                                <div className="flex items-center gap-1">
                                  {submission.reference_number}
                                  <ExternalLink className="h-3 w-3 text-muted-foreground" />
                                </div>
                              </TableCell>
                              <TableCell>
                                <div className="max-w-[250px]">
                                  <div className="font-medium text-sm truncate">{submission.title}</div>
                                  {submission.notes && (
                                    <div className="text-xs text-muted-foreground truncate mt-0.5">
                                      {submission.notes}
                                    </div>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{submission.submission_type.replace(/_/g, " ")}</Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex items-center gap-1.5">
                                  <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                                  <span className="text-sm">{submission.regulatory_body}</span>
                                </div>
                              </TableCell>
                              <TableCell>{getStatusBadge(submission.status)}</TableCell>
                              <TableCell>{getPriorityBadge(submission.priority)}</TableCell>
                              <TableCell className="text-sm">{submission.assigned_to}</TableCell>
                              <TableCell className="text-sm">{formatDate(submission.submitted_date)}</TableCell>
                              <TableCell>
                                <div className="text-sm">
                                  {formatDate(submission.expected_response_date)}
                                  {isOverdue(submission) && (
                                    <div className="flex items-center gap-1 text-xs text-red-600 mt-0.5">
                                      <AlertTriangle className="h-3 w-3" />
                                      Overdue
                                    </div>
                                  )}
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            ))}
          </Tabs>
        </>
      )}
    </div>
  );
}
