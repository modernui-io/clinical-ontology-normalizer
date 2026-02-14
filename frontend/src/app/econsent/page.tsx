"use client";

import { useState, useEffect } from "react";
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
  FileCheck,
  Users,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  PenTool,
} from "lucide-react";

interface EConsent {
  id: string;
  patient_id: string;
  trial_id: string;
  document_id: string;
  site_id: string;
  status: "signed" | "in_progress" | "withdrawn" | "expired";
  started_at: string;
  completed_at: string | null;
  consent_type: "main_study" | "sub_study" | "biobank" | "genetic";
  version: string;
  language: string;
  witness_name: string | null;
  ip_address: string | null;
}

interface EConsentResponse {
  items: EConsent[];
  total: number;
}

const statusColors: Record<EConsent["status"], string> = {
  signed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  in_progress: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  withdrawn: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  expired: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
};

const consentTypeColors: Record<EConsent["consent_type"], string> = {
  main_study: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  sub_study: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  biobank: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  genetic: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
};

const consentTypeLabels: Record<EConsent["consent_type"], string> = {
  main_study: "Main Study",
  sub_study: "Sub-Study",
  biobank: "Biobank",
  genetic: "Genetic",
};

function formatDate(isoDate: string | null): string {
  if (!isoDate) return "-";
  const date = new Date(isoDate);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function EConsentPage() {
  const [consents, setConsents] = useState<EConsent[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConsents = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/econsent/consents");
      if (!response.ok) {
        throw new Error("Failed to fetch eConsent data");
      }
      const data: EConsentResponse = await response.json();
      setConsents(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setConsents([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchConsents();
  }, []);

  // Calculate summary stats
  const signed = consents.filter((c) => c.status === "signed").length;
  const inProgress = consents.filter((c) => c.status === "in_progress").length;
  const withdrawn = consents.filter((c) => c.status === "withdrawn").length;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">eConsent Management</h1>
          <p className="text-muted-foreground">
            Track and manage electronic informed consent across clinical trials
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchConsents}
          disabled={isLoading}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Consents */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Consents</CardTitle>
            <FileCheck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "--" : total.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {isLoading ? "Loading..." : "across all trials"}
            </p>
          </CardContent>
        </Card>

        {/* Signed */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Signed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {isLoading ? "--" : signed.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {isLoading
                ? "Loading..."
                : total > 0
                ? `${Math.round((signed / total) * 100)}% of total`
                : "0% of total"}
            </p>
          </CardContent>
        </Card>

        {/* In Progress */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <PenTool className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {isLoading ? "--" : inProgress.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {isLoading ? "Loading..." : "started but not completed"}
            </p>
          </CardContent>
        </Card>

        {/* Withdrawn */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Withdrawn</CardTitle>
            <Users className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {isLoading ? "--" : withdrawn.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {isLoading ? "Loading..." : "consent withdrawn"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Consents Table */}
      <Card>
        <CardHeader>
          <CardTitle>Consent Records</CardTitle>
          <CardDescription>
            {isLoading
              ? "Loading consent records..."
              : `Showing ${consents.length} of ${total} consent records`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
              <p className="text-lg font-semibold text-red-600">Error Loading Data</p>
              <p className="text-sm text-muted-foreground mt-2">{error}</p>
              <Button onClick={fetchConsents} className="mt-4" variant="outline">
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry
              </Button>
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">Loading consents...</span>
            </div>
          ) : consents.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <FileCheck className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No consent records found</p>
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient ID</TableHead>
                    <TableHead>Trial</TableHead>
                    <TableHead>Site</TableHead>
                    <TableHead>Consent Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Language</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Completed</TableHead>
                    <TableHead>Witness</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {consents.map((consent) => (
                    <TableRow key={consent.id}>
                      <TableCell className="font-mono text-sm">
                        {consent.patient_id}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {consent.trial_id}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {consent.site_id}
                      </TableCell>
                      <TableCell>
                        <Badge className={consentTypeColors[consent.consent_type]}>
                          {consentTypeLabels[consent.consent_type]}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusColors[consent.status]}>
                          {consent.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {consent.version}
                      </TableCell>
                      <TableCell className="uppercase text-sm">
                        {consent.language}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDate(consent.started_at)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDate(consent.completed_at)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {consent.witness_name || "-"}
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
