"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Button } from "@/components/ui/button";
import {
  Lock,
  Unlock,
  AlertTriangle,
  RefreshCw,
  Loader2,
  AlertCircle,
  Eye,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UnblindingRequest {
  id: string;
  trial_id: string;
  site_id: string;
  subject_id: string;
  requestor_name: string;
  requestor_role: string;
  unblinding_reason: string;
  clinical_justification: string;
  urgency: string;
  status: string;
  requested_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  treatment_arm: string | null;
  was_unblinded: boolean;
}

interface UnblindingResponse {
  items: UnblindingRequest[];
  total: number;
}

// ---------------------------------------------------------------------------
// Badge color maps
// ---------------------------------------------------------------------------

const reasonColors: Record<string, string> = {
  overdose: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  sae: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
  medical_emergency: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  regulatory: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  study_completion: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
};

const urgencyColors: Record<string, string> = {
  EMERGENCY: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  URGENT: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
  ROUTINE: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
};

const statusColors: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  APPROVED: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  DENIED: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  WITHDRAWN: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function UnblindingPage() {
  const [requests, setRequests] = useState<UnblindingRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/emergency-unblinding/requests");
      if (!res.ok) throw new Error(`Failed to fetch unblinding requests (${res.status})`);
      const data: UnblindingResponse = await res.json();
      setRequests(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unknown error occurred");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  // Derived stats
  const totalCount = requests.length;
  const approvedCount = requests.filter((r) => r.status === "APPROVED").length;
  const pendingCount = requests.filter((r) => r.status === "PENDING").length;
  const emergencyCount = requests.filter((r) => r.urgency === "EMERGENCY").length;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-muted-foreground">Loading unblinding requests...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <AlertCircle className="h-10 w-10 text-red-500" />
        <p className="text-red-600 font-medium">{error}</p>
        <Button variant="outline" size="sm" onClick={fetchRequests}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Lock className="h-6 w-6 text-amber-600" />
            Emergency Unblinding
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track and manage emergency unblinding requests across trials
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchRequests}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
            <Eye className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Approved</CardTitle>
            <Unlock className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{approvedCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <AlertCircle className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{pendingCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Emergency</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{emergencyCount}</div>
          </CardContent>
        </Card>
      </div>

      {/* Requests Table */}
      <Card>
        <CardHeader>
          <CardTitle>Unblinding Requests</CardTitle>
          <CardDescription>
            Showing {requests.length} of {totalCount} emergency unblinding requests
          </CardDescription>
        </CardHeader>
        <CardContent>
          {requests.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              No unblinding requests found
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Site</TableHead>
                    <TableHead>Requestor</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Urgency</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Was Unblinded</TableHead>
                    <TableHead>Requested Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {requests.map((request) => (
                    <TableRow key={request.id}>
                      <TableCell className="font-mono text-sm">
                        {request.id}
                      </TableCell>
                      <TableCell className="font-medium">
                        {request.subject_id}
                      </TableCell>
                      <TableCell>{request.site_id}</TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{request.requestor_name}</span>
                          <span className="text-xs text-muted-foreground">
                            {request.requestor_role}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={reasonColors[request.unblinding_reason] || ""}>
                          {request.unblinding_reason.replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={urgencyColors[request.urgency] || ""}>
                          {request.urgency}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusColors[request.status] || ""}>
                          {request.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span
                          className={
                            request.was_unblinded
                              ? "text-green-600 font-semibold"
                              : "text-muted-foreground"
                          }
                        >
                          {request.was_unblinded ? "Y" : "N"}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(request.requested_at).toLocaleDateString()}
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
