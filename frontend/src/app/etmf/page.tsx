"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
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
  FileText,
  FolderOpen,
  RefreshCw,
  Loader2,
  AlertCircle,
  Search,
  CheckCircle,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface ETMFDocument {
  id: string;
  trial_id: string;
  zone: string;
  artifact_type: string;
  title: string;
  description: string;
  version: string;
  status: "DRAFT" | "APPROVED" | "FINAL" | "SUPERSEDED" | "EXPIRED";
  file_path: string;
  uploaded_by: string;
  uploaded_at: string;
  expiry_date: string | null;
  tags: string[];
  completeness_score: number;
}

interface ETMFResponse {
  items: ETMFDocument[];
  total: number;
}

// ============================================================================
// Constants
// ============================================================================

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-yellow-500 text-yellow-50",
  APPROVED: "bg-green-500 text-green-50",
  FINAL: "bg-blue-500 text-blue-50",
  SUPERSEDED: "bg-gray-500 text-gray-50",
  EXPIRED: "bg-red-500 text-red-50",
};

const ZONE_COLORS: Record<string, string> = {
  ZONE_01_TRIAL_MASTER_FILE: "bg-purple-100 text-purple-800 border-purple-200",
  ZONE_02_CENTRAL_TRIAL_DOCS: "bg-indigo-100 text-indigo-800 border-indigo-200",
  ZONE_03_CENTRAL_IRB_EC: "bg-blue-100 text-blue-800 border-blue-200",
  ZONE_04_CENTRAL_REGULATORY: "bg-cyan-100 text-cyan-800 border-cyan-200",
  ZONE_05_CENTRAL_VENDOR: "bg-teal-100 text-teal-800 border-teal-200",
  ZONE_06_IP_MANAGEMENT: "bg-green-100 text-green-800 border-green-200",
  ZONE_07_SAFETY_REPORTING: "bg-amber-100 text-amber-800 border-amber-200",
  ZONE_08_SITE_MGMT: "bg-orange-100 text-orange-800 border-orange-200",
};

// ============================================================================
// API Call
// ============================================================================

async function fetchETMFDocuments(): Promise<ETMFResponse> {
  const response = await fetch("/api/etmf/documents");
  if (!response.ok) {
    throw new Error(`Failed to fetch eTMF documents: ${response.statusText}`);
  }
  return response.json();
}

// ============================================================================
// Component
// ============================================================================

export default function ETMFPage() {
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch eTMF documents
  const { data, isLoading, error, refetch } = useQuery<ETMFResponse>({
    queryKey: ["etmf", "documents"],
    queryFn: fetchETMFDocuments,
  });

  const documents = useMemo(() => data?.items || [], [data?.items]);
  const totalDocuments = data?.total || 0;

  // Filter documents by search query
  const filteredDocuments = useMemo(() => {
    if (!searchQuery.trim()) {
      return documents;
    }
    const query = searchQuery.toLowerCase();
    return documents.filter(
      (doc) =>
        doc.title.toLowerCase().includes(query) ||
        doc.description.toLowerCase().includes(query) ||
        doc.artifact_type.toLowerCase().includes(query) ||
        doc.zone.toLowerCase().includes(query) ||
        doc.uploaded_by.toLowerCase().includes(query)
    );
  }, [documents, searchQuery]);

  // Calculate summary stats
  const stats = useMemo(() => {
    const draftCount = documents.filter((d) => d.status === "DRAFT").length;
    const approvedCount = documents.filter(
      (d) => d.status === "APPROVED" || d.status === "FINAL"
    ).length;
    const avgCompleteness =
      documents.length > 0
        ? Math.round(
            (documents.reduce((sum, d) => sum + d.completeness_score, 0) /
              documents.length) *
              100
          )
        : 0;

    return {
      total: totalDocuments,
      draft: draftCount,
      approved: approvedCount,
      avgCompleteness,
    };
  }, [documents, totalDocuments]);

  // Format zone label for display
  const formatZoneLabel = (zone: string) => {
    const zoneNumber = zone.match(/ZONE_(\d+)/)?.[1] || "";
    const zoneName = zone
      .replace(/ZONE_\d+_/, "")
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
    return `Zone ${zoneNumber}: ${zoneName}`;
  };

  // Format date for display
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Electronic Trial Master File
          </h1>
          <p className="text-muted-foreground">
            Manage trial documentation and regulatory artifacts
          </p>
        </div>
        <Button onClick={() => refetch()} variant="outline" size="sm">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Documents
            </CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              Across all zones
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Draft</CardTitle>
            <FolderOpen className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.draft}</div>
            <p className="text-xs text-muted-foreground">
              Pending approval
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Final/Approved
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.approved}</div>
            <p className="text-xs text-muted-foreground">
              Ready for inspection
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Avg Completeness
            </CardTitle>
            <FileText className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.avgCompleteness}%</div>
            <p className="text-xs text-muted-foreground">
              Documentation quality
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Search Documents</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by title, zone, artifact type, or uploader..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </CardContent>
      </Card>

      {/* Documents Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>eTMF Documents</CardTitle>
              <CardDescription>
                {isLoading
                  ? "Loading..."
                  : `Showing ${filteredDocuments.length} of ${totalDocuments} documents`}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
              <AlertCircle className="h-5 w-5" />
              <div>
                <p className="font-medium">Failed to load eTMF documents</p>
                <p className="text-sm">
                  {error instanceof Error
                    ? error.message
                    : "An unknown error occurred"}
                </p>
              </div>
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <FileText className="mx-auto h-12 w-12 opacity-20" />
              <p className="mt-4">No documents found.</p>
              <p className="mt-2 text-sm">
                {documents.length === 0
                  ? "Upload documents to get started."
                  : "Try adjusting your search query."}
              </p>
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead>Zone</TableHead>
                    <TableHead>Artifact Type</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Uploaded By</TableHead>
                    <TableHead>Upload Date</TableHead>
                    <TableHead>Completeness</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDocuments.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-medium max-w-xs">
                        <div className="truncate" title={doc.title}>
                          {doc.title}
                        </div>
                        {doc.description && (
                          <div
                            className="text-xs text-muted-foreground truncate mt-0.5"
                            title={doc.description}
                          >
                            {doc.description}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-xs ${
                            ZONE_COLORS[doc.zone] ||
                            "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {formatZoneLabel(doc.zone)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {doc.artifact_type
                          .replace(/_/g, " ")
                          .toLowerCase()
                          .replace(/\b\w/g, (c) => c.toUpperCase())}
                      </TableCell>
                      <TableCell className="text-sm font-mono">
                        {doc.version}
                      </TableCell>
                      <TableCell>
                        <Badge
                          className={`text-xs ${
                            STATUS_COLORS[doc.status] || "bg-gray-500"
                          }`}
                        >
                          {doc.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {doc.uploaded_by}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(doc.uploaded_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress
                            value={doc.completeness_score * 100}
                            className="w-16 h-2"
                          />
                          <span className="text-xs text-muted-foreground tabular-nums w-10">
                            {Math.round(doc.completeness_score * 100)}%
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
