"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BookOpen,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  ArrowUpCircle,
  Clock,
  ExternalLink,
  History,
  CalendarClock,
} from "lucide-react";

interface VocabularySummary {
  vocabulary_id: string;
  vocabulary_name: string;
  current_version: string | null;
  latest_version: string | null;
  update_available: boolean;
  total_concepts: number;
  status_breakdown: Record<string, number>;
  update_frequency: string | null;
  release_url: string | null;
  source: string | null;
  next_release_date: string | null;
}

interface VocabulariesResponse {
  vocabularies: VocabularySummary[];
  total_vocabularies: number;
  updates_available: number;
  scan_timestamp: string;
}

interface VersionHistoryEntry {
  concept_id: number;
  concept_name: string;
  vocabulary_version: string | null;
  version_date: string | null;
  status: string;
  status_changed_at: string | null;
  previous_concept_id: number | null;
}

function formatNextRelease(dateStr: string | null): { label: string; urgent: boolean } {
  if (!dateStr) return { label: "—", urgent: false };
  const now = new Date();
  const target = new Date(dateStr + "T00:00:00");
  const diffMs = target.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return { label: "Overdue", urgent: true };
  if (diffDays === 0) return { label: "Today", urgent: true };
  if (diffDays <= 7) return { label: `${diffDays}d`, urgent: true };
  if (diffDays <= 30) return { label: `${diffDays}d`, urgent: false };
  const months = Math.round(diffDays / 30);
  return { label: months <= 1 ? "~1 mo" : `~${months} mo`, urgent: false };
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active:
      "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300",
    deprecated:
      "bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-300",
    retired:
      "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300",
    merged:
      "bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-900/30 dark:text-purple-300",
  };

  return (
    <Badge variant="outline" className={`text-xs ${styles[status] || ""}`}>
      {status}
    </Badge>
  );
}

function VersionHistoryDialog({ vocabId }: { vocabId: string }) {
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<VocabularySummary | null>(null);

  const handleScan = async () => {
    setScanning(true);
    try {
      const res = await fetch(`/api/vocabularies/${vocabId}/scan`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setScanResult(data);
      }
    } catch {
      // ignore
    } finally {
      setScanning(false);
    }
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1">
          <History className="h-3.5 w-3.5" />
          Details
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            {vocabId} Details
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Button
            onClick={handleScan}
            disabled={scanning}
            variant="outline"
            className="w-full gap-2"
          >
            {scanning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Scan for Updates
          </Button>

          {scanResult && (
            <Card>
              <CardContent className="pt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Current Version</span>
                  <span className="font-mono">
                    {scanResult.current_version || "N/A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Latest Version</span>
                  <span className="font-mono">
                    {scanResult.latest_version || "N/A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Concepts</span>
                  <span>{scanResult.total_concepts.toLocaleString()}</span>
                </div>
                <Separator />
                <div className="text-xs font-medium">Status Breakdown</div>
                {Object.entries(scanResult.status_breakdown).map(
                  ([status, count]) => (
                    <div key={status} className="flex justify-between text-xs">
                      <StatusBadge status={status} />
                      <span>{count.toLocaleString()}</span>
                    </div>
                  )
                )}
                {scanResult.update_available && (
                  <div className="pt-2">
                    <Badge className="bg-amber-100 text-amber-800 border-amber-300">
                      Update Available
                    </Badge>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function VocabulariesPage() {
  const [data, setData] = useState<VocabulariesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadVocabularies = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/vocabularies");
      if (res.ok) {
        const result = await res.json();
        setData(result);
      } else {
        setError("Failed to load vocabularies");
      }
    } catch {
      setError("Network error loading vocabularies");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadVocabularies();
  }, [loadVocabularies]);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BookOpen className="h-6 w-6 text-indigo-500" />
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Vocabulary Management
              </h1>
            </div>
            <div className="flex items-center gap-2">
              {data && (
                <Badge variant="outline" className="text-xs">
                  {data.total_vocabularies} vocabularies
                </Badge>
              )}
              {data && data.updates_available > 0 && (
                <Badge className="bg-amber-100 text-amber-800 border-amber-300 text-xs gap-1">
                  <ArrowUpCircle className="h-3 w-3" />
                  {data.updates_available} updates
                </Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={loadVocabularies}
                disabled={isLoading}
                className="gap-1"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {isLoading && !data ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
          </div>
        ) : error ? (
          <Card className="mx-auto max-w-2xl">
            <CardContent className="py-8 text-center">
              <AlertCircle className="mx-auto h-12 w-12 text-red-400" />
              <p className="mt-2 text-zinc-500">{error}</p>
            </CardContent>
          </Card>
        ) : data ? (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid gap-4 md:grid-cols-3">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Vocabularies</CardDescription>
                  <CardTitle className="text-3xl">
                    {data.total_vocabularies}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Updates Available</CardDescription>
                  <CardTitle className="text-3xl flex items-center gap-2">
                    {data.updates_available}
                    {data.updates_available > 0 && (
                      <ArrowUpCircle className="h-6 w-6 text-amber-500" />
                    )}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Last Scan</CardDescription>
                  <CardTitle className="text-sm flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {data.scan_timestamp
                      ? new Date(data.scan_timestamp).toLocaleString()
                      : "Never"}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>

            {/* Vocabulary Table */}
            <Card>
              <CardHeader>
                <CardTitle>Vocabularies</CardTitle>
                <CardDescription>
                  Installed vocabularies with version and update status
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Vocabulary</TableHead>
                      <TableHead>Current Version</TableHead>
                      <TableHead>Latest Version</TableHead>
                      <TableHead className="text-right">Concepts</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Schedule</TableHead>
                      <TableHead>Next Update</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.vocabularies.map((vocab) => (
                      <TableRow key={vocab.vocabulary_id}>
                        <TableCell>
                          <div className="font-medium">
                            {vocab.vocabulary_name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {vocab.vocabulary_id}
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {vocab.current_version || "—"}
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {vocab.latest_version || "—"}
                        </TableCell>
                        <TableCell className="text-right">
                          {vocab.total_concepts.toLocaleString()}
                        </TableCell>
                        <TableCell>
                          {vocab.update_available ? (
                            <Badge className="bg-amber-100 text-amber-800 border-amber-300 text-xs gap-1">
                              <ArrowUpCircle className="h-3 w-3" />
                              Update
                            </Badge>
                          ) : (
                            <Badge
                              variant="outline"
                              className="text-xs gap-1 bg-green-100 text-green-800 border-green-300"
                            >
                              <CheckCircle className="h-3 w-3" />
                              Current
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="text-xs capitalize">
                            {vocab.update_frequency || "—"}
                          </div>
                          {vocab.source && (
                            <div className="text-xs text-muted-foreground">
                              {vocab.source}
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          {(() => {
                            const nr = formatNextRelease(vocab.next_release_date);
                            return (
                              <div className="flex items-center gap-1.5">
                                <CalendarClock
                                  className={`h-3.5 w-3.5 ${nr.urgent ? "text-amber-500" : "text-muted-foreground"}`}
                                />
                                <span
                                  className={`text-xs ${nr.urgent ? "font-medium text-amber-700" : "text-muted-foreground"}`}
                                >
                                  {nr.label}
                                </span>
                              </div>
                            );
                          })()}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex gap-1 justify-end">
                            <VersionHistoryDialog vocabId={vocab.vocabulary_id} />
                            {vocab.release_url && (
                              <Button
                                variant="ghost"
                                size="sm"
                                asChild
                                className="gap-1"
                              >
                                <a
                                  href={vocab.release_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                    {data.vocabularies.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={8}
                          className="text-center py-8 text-muted-foreground"
                        >
                          No vocabularies found in the database
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        ) : null}
      </main>
    </div>
  );
}
