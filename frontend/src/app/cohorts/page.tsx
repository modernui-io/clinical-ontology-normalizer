"use client";

import { useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
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
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Plus,
  Search,
  Filter,
  RefreshCw,
  MoreHorizontal,
  Users,
  Eye,
  Edit,
  Trash2,
  Copy,
  GitCompare,
  Download,
  FileJson,
  Database,
  CheckCircle,
  Clock,
  Archive,
  Tag,
} from "lucide-react";

// Types
interface CohortSummary {
  id: string;
  name: string;
  description: string | null;
  version: string;
  status: "draft" | "active" | "archived";
  criteria_count: number;
  patient_count: number | null;
  created_at: string;
  updated_at: string;
  tags: string[];
}

interface CohortListResponse {
  cohorts: CohortSummary[];
  total: number;
  offset: number;
  limit: number;
}

// API functions
const API_BASE = "/api/v1/cohorts";

async function fetchCohorts(params: {
  status?: string;
  search?: string;
  tags?: string[];
  offset?: number;
  limit?: number;
}): Promise<CohortListResponse> {
  const searchParams = new URLSearchParams();
  if (params.status && params.status !== "all") searchParams.set("status", params.status);
  if (params.search) searchParams.set("search", params.search);
  if (params.tags && params.tags.length > 0) {
    params.tags.forEach(tag => searchParams.append("tags", tag));
  }
  if (params.offset) searchParams.set("offset", String(params.offset));
  if (params.limit) searchParams.set("limit", String(params.limit));

  const response = await fetch(`${API_BASE}?${searchParams.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to fetch cohorts");
  }
  return response.json();
}

async function deleteCohort(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Failed to delete cohort");
  }
}

async function cloneCohort(id: string, newName: string): Promise<CohortSummary> {
  const response = await fetch(`${API_BASE}/${id}/clone?new_name=${encodeURIComponent(newName)}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("Failed to clone cohort");
  }
  return response.json();
}

// Status colors and icons
const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  draft: {
    color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    icon: <Clock className="h-3 w-3" />,
    label: "Draft",
  },
  active: {
    color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    icon: <CheckCircle className="h-3 w-3" />,
    label: "Active",
  },
  archived: {
    color: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
    icon: <Archive className="h-3 w-3" />,
    label: "Archived",
  },
};

export default function CohortsPage() {
  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [cloneDialogOpen, setCloneDialogOpen] = useState(false);
  const [selectedCohort, setSelectedCohort] = useState<CohortSummary | null>(null);
  const [cloneName, setCloneName] = useState("");

  // Fetch cohorts
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["cohorts", statusFilter, searchQuery, page, pageSize],
    queryFn: () =>
      fetchCohorts({
        status: statusFilter !== "all" ? statusFilter : undefined,
        search: searchQuery || undefined,
        offset: (page - 1) * pageSize,
        limit: pageSize,
      }),
  });

  const cohorts = useMemo(() => data?.cohorts || [], [data?.cohorts]);
  const totalCohorts = data?.total || 0;
  const totalPages = Math.ceil(totalCohorts / pageSize);

  // Status counts
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { draft: 0, active: 0, archived: 0 };
    cohorts.forEach((c) => {
      if (counts[c.status] !== undefined) {
        counts[c.status]++;
      }
    });
    return counts;
  }, [cohorts]);

  // Total patients across all cohorts
  const totalPatients = useMemo(() => {
    return cohorts.reduce((sum, c) => sum + (c.patient_count || 0), 0);
  }, [cohorts]);

  // Clear filters
  const handleClearFilters = useCallback(() => {
    setStatusFilter("all");
    setSearchQuery("");
    setPage(1);
  }, []);

  // Actions
  const handleDelete = useCallback(async () => {
    if (!selectedCohort) return;
    try {
      await deleteCohort(selectedCohort.id);
      toast.success(`Cohort "${selectedCohort.name}" deleted`);
      setDeleteDialogOpen(false);
      setSelectedCohort(null);
      refetch();
    } catch {
      toast.error("Failed to delete cohort");
    }
  }, [selectedCohort, refetch]);

  const handleClone = useCallback(async () => {
    if (!selectedCohort || !cloneName.trim()) return;
    try {
      await cloneCohort(selectedCohort.id, cloneName.trim());
      toast.success(`Cohort cloned as "${cloneName}"`);
      setCloneDialogOpen(false);
      setSelectedCohort(null);
      setCloneName("");
      refetch();
    } catch {
      toast.error("Failed to clone cohort");
    }
  }, [selectedCohort, cloneName, refetch]);

  const handleExport = useCallback((id: string, format: "json" | "sql") => {
    window.open(`${API_BASE}/${id}/export?format=${format}`, "_blank");
  }, []);

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Cohort Builder</h1>
          <p className="text-muted-foreground">
            Create and manage patient cohorts for research and analytics
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/cohorts/compare">
            <Button variant="outline">
              <GitCompare className="mr-2 h-4 w-4" />
              Compare Cohorts
            </Button>
          </Link>
          <Link href="/cohorts/builder">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              New Cohort
            </Button>
          </Link>
        </div>
      </div>

      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Cohorts</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalCohorts}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Patients</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalPatients.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Active Cohorts</CardTitle>
              <CheckCircle className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{statusCounts.active}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Draft Cohorts</CardTitle>
              <Clock className="h-4 w-4 text-yellow-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{statusCounts.draft}</div>
            </CardContent>
          </Card>
        </div>

        {/* Filters Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Filter className="h-5 w-5" />
              Filters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {/* Search */}
              <div className="lg:col-span-2">
                <label className="text-sm font-medium text-zinc-500">Search</label>
                <div className="relative mt-1">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by name or description..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setPage(1);
                    }}
                    className="pl-8"
                  />
                </div>
              </div>

              {/* Status Filter */}
              <div>
                <label className="text-sm font-medium text-zinc-500">Status</label>
                <select
                  className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="all">All Statuses</option>
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="archived">Archived</option>
                </select>
              </div>

              {/* Actions */}
              <div className="flex items-end">
                <Button variant="ghost" size="sm" onClick={handleClearFilters}>
                  Clear Filters
                </Button>
              </div>
            </div>

            {/* Filter Badges */}
            <div className="mt-4 flex flex-wrap gap-2">
              {Object.entries(STATUS_CONFIG).map(([status, config]) => (
                <Badge
                  key={status}
                  variant="outline"
                  className={`cursor-pointer ${statusFilter === status ? "ring-2 ring-blue-500" : ""}`}
                  onClick={() =>
                    setStatusFilter(statusFilter === status ? "all" : status)
                  }
                >
                  {config.icon}
                  <span className="ml-1.5">
                    {config.label}: {statusCounts[status] || 0}
                  </span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Cohorts Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Cohort Definitions</CardTitle>
                <CardDescription>
                  {isLoading
                    ? "Loading..."
                    : `Showing ${cohorts.length} of ${totalCohorts} cohorts`}
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
                Failed to load cohorts. Is the backend running?
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
              </div>
            ) : cohorts.length === 0 ? (
              <div className="py-12 text-center text-zinc-500">
                <Database className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-4">No cohorts found.</p>
                <p className="mt-2 text-sm">
                  {totalCohorts === 0
                    ? "Create a new cohort to get started."
                    : "Try adjusting your filters."}
                </p>
                <Link href="/cohorts/builder">
                  <Button className="mt-4">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Cohort
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Criteria</TableHead>
                      <TableHead>Patients</TableHead>
                      <TableHead>Version</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cohorts.map((cohort) => (
                      <TableRow key={cohort.id}>
                        <TableCell>
                          <div>
                            <Link
                              href={`/cohorts/${cohort.id}`}
                              className="font-medium text-blue-600 hover:underline"
                            >
                              {cohort.name}
                            </Link>
                            {cohort.description && (
                              <p className="text-xs text-muted-foreground line-clamp-1 mt-1">
                                {cohort.description}
                              </p>
                            )}
                            {cohort.tags.length > 0 && (
                              <div className="flex gap-1 mt-1">
                                {cohort.tags.slice(0, 2).map((tag) => (
                                  <Badge key={tag} variant="outline" className="text-xs">
                                    <Tag className="h-2 w-2 mr-1" />
                                    {tag}
                                  </Badge>
                                ))}
                                {cohort.tags.length > 2 && (
                                  <Badge variant="outline" className="text-xs">
                                    +{cohort.tags.length - 2}
                                  </Badge>
                                )}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className={STATUS_CONFIG[cohort.status]?.color}>
                            {STATUS_CONFIG[cohort.status]?.icon}
                            <span className="ml-1">{STATUS_CONFIG[cohort.status]?.label}</span>
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm">{cohort.criteria_count} criteria</span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Users className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">
                              {cohort.patient_count?.toLocaleString() || "N/A"}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            v{cohort.version}
                          </code>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm text-muted-foreground">
                            {new Date(cohort.updated_at).toLocaleDateString()}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem asChild>
                                <Link href={`/cohorts/${cohort.id}`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem asChild>
                                <Link href={`/cohorts/builder?edit=${cohort.id}`}>
                                  <Edit className="mr-2 h-4 w-4" />
                                  Edit
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => {
                                  setSelectedCohort(cohort);
                                  setCloneName(`${cohort.name} (Copy)`);
                                  setCloneDialogOpen(true);
                                }}
                              >
                                <Copy className="mr-2 h-4 w-4" />
                                Clone
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem asChild>
                                <Link href={`/cohorts/compare?a=${cohort.id}`}>
                                  <GitCompare className="mr-2 h-4 w-4" />
                                  Compare
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                onClick={() => handleExport(cohort.id, "json")}
                              >
                                <FileJson className="mr-2 h-4 w-4" />
                                Export JSON
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => handleExport(cohort.id, "sql")}
                              >
                                <Download className="mr-2 h-4 w-4" />
                                Export SQL
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="text-red-600"
                                onClick={() => {
                                  setSelectedCohort(cohort);
                                  setDeleteDialogOpen(true);
                                }}
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-500">Rows per page:</span>
                  <select
                    className="rounded-md border px-2 py-1 text-sm"
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setPage(1);
                    }}
                  >
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-500">
                    Page {page} of {totalPages}
                  </span>
                  <div className="flex gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page === 1}
                      onClick={() => setPage(1)}
                    >
                      First
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page === 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Prev
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page === totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Next
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page === totalPages}
                      onClick={() => setPage(totalPages)}
                    >
                      Last
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Cohort</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &quot;{selectedCohort?.name}&quot;? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Clone Dialog */}
      <Dialog open={cloneDialogOpen} onOpenChange={setCloneDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clone Cohort</DialogTitle>
            <DialogDescription>
              Create a copy of &quot;{selectedCohort?.name}&quot; with a new name.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <label className="text-sm font-medium">New Cohort Name</label>
            <Input
              value={cloneName}
              onChange={(e) => setCloneName(e.target.value)}
              placeholder="Enter name for the cloned cohort"
              className="mt-1"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCloneDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleClone} disabled={!cloneName.trim()}>
              Clone
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
