"use client";

import { useState, useMemo, useCallback } from "react";
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
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDocuments } from "@/hooks/use-api";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-yellow-500",
  processing: "bg-blue-500",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

type SortField = "created_at" | "status" | "patient_id" | "note_type";
type SortDirection = "asc" | "desc";

interface SortConfig {
  field: SortField;
  direction: SortDirection;
}

export default function DocumentsPage() {
  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [dateRangeStart, setDateRangeStart] = useState("");
  const [dateRangeEnd, setDateRangeEnd] = useState("");

  // Sort state
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    field: "created_at",
    direction: "desc",
  });

  // Selection state for bulk actions
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Fetch documents using React Query hook
  const { data, isLoading, error, refetch } = useDocuments({ page, page_size: pageSize });

  const documents = useMemo(() => data?.documents || [], [data?.documents]);
  const totalDocuments = data?.total || 0;
  const totalPages = Math.ceil(totalDocuments / pageSize);

  // Filter and sort documents
  const filteredAndSortedDocuments = useMemo(() => {
    let filtered = [...documents];

    // Apply status filter
    if (statusFilter !== "all") {
      filtered = filtered.filter((doc) => doc.status === statusFilter);
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (doc) =>
          doc.patient_id.toLowerCase().includes(query) ||
          doc.note_type.toLowerCase().includes(query) ||
          doc.text.toLowerCase().includes(query) ||
          doc.id.toLowerCase().includes(query)
      );
    }

    // Apply date range filter
    if (dateRangeStart) {
      const startDate = new Date(dateRangeStart);
      filtered = filtered.filter(
        (doc) => new Date(doc.created_at) >= startDate
      );
    }
    if (dateRangeEnd) {
      const endDate = new Date(dateRangeEnd);
      endDate.setHours(23, 59, 59, 999);
      filtered = filtered.filter((doc) => new Date(doc.created_at) <= endDate);
    }

    // Apply sorting
    filtered.sort((a, b) => {
      let aValue: string | number | Date;
      let bValue: string | number | Date;

      switch (sortConfig.field) {
        case "created_at":
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
        case "status":
          aValue = a.status;
          bValue = b.status;
          break;
        case "patient_id":
          aValue = a.patient_id;
          bValue = b.patient_id;
          break;
        case "note_type":
          aValue = a.note_type;
          bValue = b.note_type;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [documents, statusFilter, searchQuery, dateRangeStart, dateRangeEnd, sortConfig]);

  // Handle column header click for sorting
  const handleSort = useCallback((field: SortField) => {
    setSortConfig((current) => ({
      field,
      direction:
        current.field === field && current.direction === "asc" ? "desc" : "asc",
    }));
  }, []);

  // Get sort indicator for column headers
  const getSortIndicator = (field: SortField) => {
    if (sortConfig.field !== field) return null;
    return sortConfig.direction === "asc" ? " \u2191" : " \u2193";
  };

  // Handle row selection
  const handleSelectAll = useCallback(() => {
    if (selectedIds.size === filteredAndSortedDocuments.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredAndSortedDocuments.map((doc) => doc.id)));
    }
  }, [filteredAndSortedDocuments, selectedIds.size]);

  const handleSelectRow = useCallback((id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  // Bulk actions
  const handleBulkDelete = useCallback(() => {
    // In a real implementation, this would call the API
    toast.error("Bulk delete is not yet implemented in the backend");
  }, []);

  const handleBulkReprocess = useCallback(() => {
    // In a real implementation, this would call the API
    toast.error("Bulk reprocess is not yet implemented in the backend");
  }, []);

  // Clear filters
  const handleClearFilters = useCallback(() => {
    setStatusFilter("all");
    setSearchQuery("");
    setDateRangeStart("");
    setDateRangeEnd("");
  }, []);

  // Count documents by status
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {
      queued: 0,
      processing: 0,
      completed: 0,
      failed: 0,
    };
    documents.forEach((doc) => {
      if (counts[doc.status] !== undefined) {
        counts[doc.status]++;
      }
    });
    return counts;
  }, [documents]);

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Documents</h1>
          <p className="text-muted-foreground">
            View and manage clinical documents
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/documents/compare">
            <Button variant="outline">Compare Documents</Button>
          </Link>
          <Link href="/documents/upload">
            <Button>Upload Document</Button>
          </Link>
        </div>
      </div>

      <div className="space-y-6">
        {/* Filters Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Filters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
              {/* Search */}
              <div className="lg:col-span-2">
                <label className="text-sm font-medium text-zinc-500">
                  Search
                </label>
                <Input
                  placeholder="Search by patient ID, note type, or content..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="mt-1"
                />
              </div>

              {/* Status Filter */}
              <div>
                <label className="text-sm font-medium text-zinc-500">
                  Status
                </label>
                <select
                  className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="all">All Statuses</option>
                  <option value="queued">Queued ({statusCounts.queued})</option>
                  <option value="processing">
                    Processing ({statusCounts.processing})
                  </option>
                  <option value="completed">
                    Completed ({statusCounts.completed})
                  </option>
                  <option value="failed">Failed ({statusCounts.failed})</option>
                </select>
              </div>

              {/* Date Range Start */}
              <div>
                <label className="text-sm font-medium text-zinc-500">
                  From Date
                </label>
                <Input
                  type="date"
                  value={dateRangeStart}
                  onChange={(e) => setDateRangeStart(e.target.value)}
                  className="mt-1"
                />
              </div>

              {/* Date Range End */}
              <div>
                <label className="text-sm font-medium text-zinc-500">
                  To Date
                </label>
                <Input
                  type="date"
                  value={dateRangeEnd}
                  onChange={(e) => setDateRangeEnd(e.target.value)}
                  className="mt-1"
                />
              </div>
            </div>

            {/* Filter Actions */}
            <div className="mt-4 flex items-center justify-between">
              <div className="flex flex-wrap gap-2">
                {Object.entries(statusCounts).map(([status, count]) => (
                  <Badge
                    key={status}
                    variant="outline"
                    className={`cursor-pointer ${statusFilter === status ? "ring-2 ring-blue-500" : ""}`}
                    onClick={() =>
                      setStatusFilter(statusFilter === status ? "all" : status)
                    }
                  >
                    <span
                      className={`mr-1.5 inline-block h-2 w-2 rounded-full ${STATUS_COLORS[status]}`}
                    />
                    {status}: {count}
                  </Badge>
                ))}
              </div>
              <Button variant="ghost" size="sm" onClick={handleClearFilters}>
                Clear Filters
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Bulk Actions */}
        {selectedIds.size > 0 && (
          <Card>
            <CardContent className="py-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-600">
                  {selectedIds.size} document(s) selected
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleBulkReprocess}
                  >
                    Reprocess Selected
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleBulkDelete}
                  >
                    Delete Selected
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Documents Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Document List</CardTitle>
                <CardDescription>
                  {isLoading
                    ? "Loading..."
                    : `Showing ${filteredAndSortedDocuments.length} of ${totalDocuments} documents`}
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
                Failed to load documents. Is the backend running?
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
              </div>
            ) : filteredAndSortedDocuments.length === 0 ? (
              <div className="py-12 text-center text-zinc-500">
                <p>No documents found.</p>
                <p className="mt-2 text-sm">
                  {documents.length === 0
                    ? "Upload a document to get started."
                    : "Try adjusting your filters."}
                </p>
              </div>
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <input
                          type="checkbox"
                          checked={
                            selectedIds.size ===
                              filteredAndSortedDocuments.length &&
                            filteredAndSortedDocuments.length > 0
                          }
                          onChange={handleSelectAll}
                          className="h-4 w-4 rounded border-gray-300"
                        />
                      </TableHead>
                      <TableHead
                        className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800"
                        onClick={() => handleSort("patient_id")}
                      >
                        Patient{getSortIndicator("patient_id")}
                      </TableHead>
                      <TableHead
                        className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800"
                        onClick={() => handleSort("note_type")}
                      >
                        Note Type{getSortIndicator("note_type")}
                      </TableHead>
                      <TableHead
                        className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800"
                        onClick={() => handleSort("status")}
                      >
                        Status{getSortIndicator("status")}
                      </TableHead>
                      <TableHead
                        className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800"
                        onClick={() => handleSort("created_at")}
                      >
                        Created{getSortIndicator("created_at")}
                      </TableHead>
                      <TableHead>Preview</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAndSortedDocuments.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <input
                            type="checkbox"
                            checked={selectedIds.has(doc.id)}
                            onChange={() => handleSelectRow(doc.id)}
                            className="h-4 w-4 rounded border-gray-300"
                          />
                        </TableCell>
                        <TableCell className="font-medium">
                          <Link
                            href={`/patients/${doc.patient_id}`}
                            className="text-blue-600 hover:underline"
                          >
                            {doc.patient_id}
                          </Link>
                        </TableCell>
                        <TableCell>{doc.note_type}</TableCell>
                        <TableCell>
                          <Badge
                            className={
                              STATUS_COLORS[doc.status] || "bg-gray-500"
                            }
                          >
                            {doc.status.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {new Date(doc.created_at).toLocaleDateString()}{" "}
                          <span className="text-zinc-500">
                            {new Date(doc.created_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </TableCell>
                        <TableCell className="max-w-xs truncate text-sm text-zinc-500">
                          {doc.text.substring(0, 80)}...
                        </TableCell>
                        <TableCell className="text-right">
                          <Link href={`/documents/${doc.id}`}>
                            <Button variant="ghost" size="sm">
                              View
                            </Button>
                          </Link>
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
