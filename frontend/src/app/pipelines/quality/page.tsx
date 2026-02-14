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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Gauge,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Database,
} from "lucide-react";

interface CompletenessScore {
  table_name: string;
  total_rows: number;
  non_null_count: number;
  completeness_pct: number;
}

interface ConsistencyCheck {
  check_name: string;
  status: string;
  details: string;
  checked_at: string;
}

export default function DataQualityPage() {
  const [completeness, setCompleteness] = useState<CompletenessScore[]>([]);
  const [consistency, setConsistency] = useState<ConsistencyCheck[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [compRes, consRes] = await Promise.all([
        fetch("/api/data-quality/completeness"),
        fetch("/api/data-quality/consistency"),
      ]);
      if (compRes.ok) {
        const data = await compRes.json();
        setCompleteness(Array.isArray(data) ? data : data.items || []);
      }
      if (consRes.ok) {
        const data = await consRes.json();
        setConsistency(Array.isArray(data) ? data : data.items || []);
      }
    } catch {
      setError("Failed to load data quality metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const avgCompleteness =
    completeness.length > 0
      ? completeness.reduce((sum, c) => sum + c.completeness_pct, 0) / completeness.length
      : 0;

  const passedChecks = consistency.filter((c) => c.status === "passed").length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Gauge className="h-6 w-6 text-indigo-600" />
            Data Quality
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Completeness scores and consistency checks across pipeline tables
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
          {loading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Refresh
        </Button>
      </div>

      {error ? (
        <Card>
          <CardContent className="py-8 text-center">
            <AlertCircle className="mx-auto h-12 w-12 text-red-400" />
            <p className="mt-2 text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      ) : loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Summary */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Avg Completeness</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{avgCompleteness.toFixed(1)}%</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Across {completeness.length} tables
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Consistency Checks</CardTitle>
                <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {passedChecks}/{consistency.length}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Checks passed</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Tables Monitored</CardTitle>
                <Database className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{completeness.length}</div>
                <p className="text-xs text-muted-foreground mt-1">Active tables</p>
              </CardContent>
            </Card>
          </div>

          {/* Completeness Table */}
          <Card>
            <CardHeader>
              <CardTitle>Table Completeness</CardTitle>
              <CardDescription>
                Non-null field coverage per table
              </CardDescription>
            </CardHeader>
            <CardContent>
              {completeness.length === 0 ? (
                <p className="py-8 text-center text-muted-foreground">
                  No completeness data available
                </p>
              ) : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Table</TableHead>
                        <TableHead className="text-right">Total Rows</TableHead>
                        <TableHead className="text-right">Non-Null</TableHead>
                        <TableHead className="text-right">Completeness</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {completeness.map((c) => (
                        <TableRow key={c.table_name}>
                          <TableCell className="font-mono text-sm">{c.table_name}</TableCell>
                          <TableCell className="text-right tabular-nums">
                            {c.total_rows.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {c.non_null_count.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            <Badge
                              className={
                                c.completeness_pct >= 95
                                  ? "bg-green-100 text-green-800"
                                  : c.completeness_pct >= 80
                                  ? "bg-yellow-100 text-yellow-800"
                                  : "bg-red-100 text-red-800"
                              }
                            >
                              {c.completeness_pct.toFixed(1)}%
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Consistency Checks */}
          <Card>
            <CardHeader>
              <CardTitle>Consistency Checks</CardTitle>
              <CardDescription>
                Cross-table referential integrity and business rule validation
              </CardDescription>
            </CardHeader>
            <CardContent>
              {consistency.length === 0 ? (
                <p className="py-8 text-center text-muted-foreground">
                  No consistency checks available
                </p>
              ) : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Check</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Details</TableHead>
                        <TableHead>Last Run</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {consistency.map((c, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-medium">{c.check_name}</TableCell>
                          <TableCell>
                            {c.status === "passed" ? (
                              <Badge className="bg-green-100 text-green-800 gap-1">
                                <CheckCircle2 className="h-3 w-3" />
                                Passed
                              </Badge>
                            ) : (
                              <Badge className="bg-red-100 text-red-800 gap-1">
                                <XCircle className="h-3 w-3" />
                                Failed
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                            {c.details}
                          </TableCell>
                          <TableCell className="text-sm">
                            {c.checked_at
                              ? new Date(c.checked_at).toLocaleString()
                              : "-"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
