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
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Plus,
  Search,
  Filter,
  RefreshCw,
  Download,
  Upload,
  MoreHorizontal,
  List,
  GitBranch,
  FileJson,
  FileSpreadsheet,
  Eye,
  Edit,
  Trash2,
  CheckCircle,
  Archive,
} from "lucide-react";

// Types
interface ValueSet {
  id: string;
  name: string;
  title: string | null;
  description: string | null;
  url: string | null;
  version: string;
  status: "draft" | "active" | "retired";
  value_set_type: "extensional" | "intensional";
  code_count: number;
  rule_count: number;
  publisher: string | null;
  purpose: string | null;
  copyright: string | null;
  experimental: boolean;
  immutable: boolean;
  created_at: string;
  updated_at: string;
}

interface ValueSetListResponse {
  value_sets: ValueSet[];
  total: number;
  offset: number;
  limit: number;
}

// API functions
const API_BASE = "/api/v1/valuesets";

async function fetchValueSets(params: {
  status?: string;
  value_set_type?: string;
  search?: string;
  offset?: number;
  limit?: number;
}): Promise<ValueSetListResponse> {
  const searchParams = new URLSearchParams();
  if (params.status) searchParams.set("status", params.status);
  if (params.value_set_type) searchParams.set("value_set_type", params.value_set_type);
  if (params.search) searchParams.set("search", params.search);
  if (params.offset) searchParams.set("offset", String(params.offset));
  if (params.limit) searchParams.set("limit", String(params.limit));

  const response = await fetch(`${API_BASE}?${searchParams.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to fetch value sets");
  }
  return response.json();
}

async function deleteValueSet(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Failed to delete value set");
  }
}

async function activateValueSet(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${id}/activate`, { method: "POST" });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to activate value set");
  }
}

async function retireValueSet(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${id}/retire`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Failed to retire value set");
  }
}

// Helper functions
const STATUS_COLORS: Record<string, string> = {
  draft: "bg-yellow-500",
  active: "bg-green-500",
  retired: "bg-gray-500",
};

const TYPE_COLORS: Record<string, string> = {
  extensional: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  intensional: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
};

export default function ValueSetsPage() {
  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Fetch value sets
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["valuesets", statusFilter, typeFilter, searchQuery, page, pageSize],
    queryFn: () =>
      fetchValueSets({
        status: statusFilter !== "all" ? statusFilter : undefined,
        value_set_type: typeFilter !== "all" ? typeFilter : undefined,
        search: searchQuery || undefined,
        offset: (page - 1) * pageSize,
        limit: pageSize,
      }),
  });

  const valueSets = useMemo(() => data?.value_sets || [], [data?.value_sets]);
  const totalValueSets = data?.total || 0;
  const totalPages = Math.ceil(totalValueSets / pageSize);

  // Status counts
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { draft: 0, active: 0, retired: 0 };
    valueSets.forEach((vs) => {
      if (counts[vs.status] !== undefined) {
        counts[vs.status]++;
      }
    });
    return counts;
  }, [valueSets]);

  // Clear filters
  const handleClearFilters = useCallback(() => {
    setStatusFilter("all");
    setTypeFilter("all");
    setSearchQuery("");
    setPage(1);
  }, []);

  // Actions
  const handleDelete = useCallback(
    async (id: string, name: string) => {
      if (!confirm(`Are you sure you want to delete "${name}"?`)) {
        return;
      }
      try {
        await deleteValueSet(id);
        toast.success(`Value set "${name}" deleted`);
        refetch();
      } catch {
        toast.error("Failed to delete value set");
      }
    },
    [refetch]
  );

  const handleActivate = useCallback(
    async (id: string, name: string) => {
      try {
        await activateValueSet(id);
        toast.success(`Value set "${name}" activated`);
        refetch();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to activate value set");
      }
    },
    [refetch]
  );

  const handleRetire = useCallback(
    async (id: string, name: string) => {
      try {
        await retireValueSet(id);
        toast.success(`Value set "${name}" retired`);
        refetch();
      } catch {
        toast.error("Failed to retire value set");
      }
    },
    [refetch]
  );

  const handleExport = useCallback((id: string, format: "fhir" | "csv") => {
    window.open(`${API_BASE}/${id}/export?format=${format}`, "_blank");
  }, []);

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Value Sets</h1>
          <p className="text-muted-foreground">
            Manage clinical terminology value sets for use in decision support and validation
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/valuesets/new">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              New Value Set
            </Button>
          </Link>
        </div>
      </div>

      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Value Sets</CardTitle>
              <List className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalValueSets}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Active</CardTitle>
              <CheckCircle className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{statusCounts.active}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Draft</CardTitle>
              <Edit className="h-4 w-4 text-yellow-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{statusCounts.draft}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Retired</CardTitle>
              <Archive className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-gray-600">{statusCounts.retired}</div>
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
                    placeholder="Search by name, title, or description..."
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
                  <option value="retired">Retired</option>
                </select>
              </div>

              {/* Type Filter */}
              <div>
                <label className="text-sm font-medium text-zinc-500">Type</label>
                <select
                  className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  value={typeFilter}
                  onChange={(e) => {
                    setTypeFilter(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="all">All Types</option>
                  <option value="extensional">Extensional</option>
                  <option value="intensional">Intensional</option>
                </select>
              </div>
            </div>

            {/* Filter Actions */}
            <div className="mt-4 flex items-center justify-between">
              <div className="flex flex-wrap gap-2">
                {Object.entries(STATUS_COLORS).map(([status, color]) => (
                  <Badge
                    key={status}
                    variant="outline"
                    className={`cursor-pointer ${statusFilter === status ? "ring-2 ring-blue-500" : ""}`}
                    onClick={() =>
                      setStatusFilter(statusFilter === status ? "all" : status)
                    }
                  >
                    <span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${color}`} />
                    {status}: {statusCounts[status] || 0}
                  </Badge>
                ))}
              </div>
              <Button variant="ghost" size="sm" onClick={handleClearFilters}>
                Clear Filters
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Value Sets Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Value Set List</CardTitle>
                <CardDescription>
                  {isLoading
                    ? "Loading..."
                    : `Showing ${valueSets.length} of ${totalValueSets} value sets`}
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => refetch()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm">
                      <Upload className="mr-2 h-4 w-4" />
                      Import
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem asChild>
                      <Link href="/valuesets/new?import=fhir">
                        <FileJson className="mr-2 h-4 w-4" />
                        Import FHIR ValueSet
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/valuesets/new?import=csv">
                        <FileSpreadsheet className="mr-2 h-4 w-4" />
                        Import CSV
                      </Link>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
                Failed to load value sets. Is the backend running?
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
              </div>
            ) : valueSets.length === 0 ? (
              <div className="py-12 text-center text-zinc-500">
                <List className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-4">No value sets found.</p>
                <p className="mt-2 text-sm">
                  {totalValueSets === 0
                    ? "Create a new value set to get started."
                    : "Try adjusting your filters."}
                </p>
                <Link href="/valuesets/new">
                  <Button className="mt-4">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Value Set
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Version</TableHead>
                      <TableHead>Codes/Rules</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {valueSets.map((vs) => (
                      <TableRow key={vs.id}>
                        <TableCell>
                          <div>
                            <Link
                              href={`/valuesets/${vs.id}`}
                              className="font-medium text-blue-600 hover:underline"
                            >
                              {vs.title || vs.name}
                            </Link>
                            {vs.description && (
                              <p className="text-xs text-muted-foreground line-clamp-1 mt-1">
                                {vs.description}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className={TYPE_COLORS[vs.value_set_type]}>
                            {vs.value_set_type === "extensional" ? (
                              <List className="mr-1 h-3 w-3" />
                            ) : (
                              <GitBranch className="mr-1 h-3 w-3" />
                            )}
                            {vs.value_set_type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={STATUS_COLORS[vs.status]}>
                            {vs.status.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            v{vs.version}
                          </code>
                        </TableCell>
                        <TableCell>
                          {vs.value_set_type === "extensional" ? (
                            <span className="text-sm">{vs.code_count} codes</span>
                          ) : (
                            <span className="text-sm">{vs.rule_count} rules</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <span className="text-sm text-muted-foreground">
                            {new Date(vs.updated_at).toLocaleDateString()}
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
                                <Link href={`/valuesets/${vs.id}`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem asChild>
                                <Link href={`/valuesets/${vs.id}?tab=expand`}>
                                  <List className="mr-2 h-4 w-4" />
                                  Expand
                                </Link>
                              </DropdownMenuItem>
                              {vs.status === "draft" && (
                                <DropdownMenuItem
                                  onClick={() => handleActivate(vs.id, vs.name)}
                                >
                                  <CheckCircle className="mr-2 h-4 w-4" />
                                  Activate
                                </DropdownMenuItem>
                              )}
                              {vs.status === "active" && (
                                <DropdownMenuItem
                                  onClick={() => handleRetire(vs.id, vs.name)}
                                >
                                  <Archive className="mr-2 h-4 w-4" />
                                  Retire
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuItem
                                onClick={() => handleExport(vs.id, "fhir")}
                              >
                                <Download className="mr-2 h-4 w-4" />
                                Export FHIR
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => handleExport(vs.id, "csv")}
                              >
                                <FileSpreadsheet className="mr-2 h-4 w-4" />
                                Export CSV
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-red-600"
                                onClick={() => handleDelete(vs.id, vs.name)}
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
    </div>
  );
}
