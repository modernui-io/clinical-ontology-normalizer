"use client";

import { useState } from "react";
import Link from "next/link";
import { useTrials, useTrialStats } from "@/hooks/api";
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
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Search,
  RefreshCw,
  Users,
  Activity,
  ClipboardList,
  Target,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

const statusColors: Record<string, string> = {
  recruiting: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  active: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  completed: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
  suspended: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  closed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
};

const phaseLabels: Record<string, string> = {
  phase_1: "Phase I",
  phase_2: "Phase II",
  phase_3: "Phase III",
  phase_4: "Phase IV",
};

export default function TrialsPage() {
  const [page, setPage] = useState(0);
  const [pageSize] = useState(25);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data, isLoading, refetch } = useTrials({
    search: searchQuery || undefined,
    status: statusFilter || undefined,
    offset: page * pageSize,
    limit: pageSize,
  });

  const { data: stats } = useTrialStats();

  const trials = data?.trials || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Clinical Trials</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage trials and screen patients for eligibility
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Trials</CardTitle>
            <ClipboardList className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(stats as Record<string, unknown>)?.total_trials as number ?? total}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Recruiting</CardTitle>
            <Target className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {((stats as Record<string, unknown>)?.trials_by_status as Record<string, number>)?.recruiting ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Enrolled</CardTitle>
            <Users className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {(stats as Record<string, unknown>)?.total_enrolled_patients as number ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg Enrollment</CardTitle>
            <Activity className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {(() => {
                const totalTrials = (stats as Record<string, unknown>)?.total_trials as number ?? 0;
                const totalEnrolled = (stats as Record<string, unknown>)?.total_enrolled_patients as number ?? 0;
                return totalTrials > 0 ? Math.round(totalEnrolled / totalTrials) : 0;
              })()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">patients per trial</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name, NCT number, sponsor..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(0);
                }}
                className="pl-10"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(0);
              }}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">All Statuses</option>
              <option value="recruiting">Recruiting</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="suspended">Suspended</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Trials Table */}
      <Card>
        <CardHeader>
          <CardTitle>Trials</CardTitle>
          <CardDescription>
            Showing {trials.length} of {total} trials
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">Loading trials...</span>
            </div>
          ) : trials.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              No trials found
            </div>
          ) : (
            <>
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Trial</TableHead>
                      <TableHead>NCT Number</TableHead>
                      <TableHead>Sponsor</TableHead>
                      <TableHead>Phase</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Enrollment</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {trials.map((trial) => (
                      <TableRow key={trial.id}>
                        <TableCell>
                          <Link
                            href={`/trials/${trial.id}`}
                            className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                          >
                            {trial.name}
                          </Link>
                          {trial.therapeutic_area && (
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {trial.therapeutic_area}
                            </p>
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {trial.nct_number || "-"}
                        </TableCell>
                        <TableCell>{trial.sponsor}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {phaseLabels[trial.phase] || trial.phase}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={statusColors[trial.status] || ""}>
                            {trial.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <span className="font-semibold">
                              {trial.enrolled_count}
                            </span>
                            <span className="text-muted-foreground">/</span>
                            <span className="text-muted-foreground">
                              {trial.enrollment_target}
                            </span>
                          </div>
                          <div className="mt-1 h-1.5 w-20 rounded-full bg-gray-200 dark:bg-gray-700 ml-auto">
                            <div
                              className="h-full rounded-full bg-blue-500"
                              style={{
                                width: `${Math.min(100, (trial.enrolled_count / trial.enrollment_target) * 100)}%`,
                              }}
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    Page {page + 1} of {totalPages}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page === 0}
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Prev
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages - 1}
                      onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
