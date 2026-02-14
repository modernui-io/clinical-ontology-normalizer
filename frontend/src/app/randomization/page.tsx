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
import { Progress } from "@/components/ui/progress";
import {
  Shuffle,
  Lock,
  Users,
  Target,
  RefreshCw,
  Loader2,
  AlertCircle,
  Eye,
  EyeOff,
} from "lucide-react";

// --- Types ---

interface Arm {
  id: string;
  name: string;
  arm_type: string;
  description: string;
  allocation_weight: number;
  current_count: number;
  target_count: number;
}

interface RandomizationScheme {
  id: string;
  trial_id: string;
  trial_name: string;
  method: string;
  blinding_level: string;
  allocation_ratio: string;
  status: string;
  arms: Arm[];
  total_randomized?: number;
  created_at?: string;
  updated_at?: string;
}

interface RandomizationResponse {
  items: RandomizationScheme[];
  total: number;
}

// --- Badge color maps ---

const methodColors: Record<string, string> = {
  BLOCK: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  STRATIFIED: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  ADAPTIVE: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  MINIMIZATION: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
};

const blindingColors: Record<string, string> = {
  OPEN_LABEL: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
  SINGLE_BLIND: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  DOUBLE_BLIND: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300",
  TRIPLE_BLIND: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
};

const statusColors: Record<string, string> = {
  ACTIVE: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  PAUSED: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  COMPLETED: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
};

const armTypeColors: Record<string, string> = {
  TREATMENT: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  PLACEBO: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
  ACTIVE_COMPARATOR: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
};

// --- Helpers ---

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function blindingIcon(level: string) {
  if (level === "OPEN_LABEL") return <Eye className="h-3 w-3 mr-1" />;
  return <EyeOff className="h-3 w-3 mr-1" />;
}

export default function RandomizationPage() {
  const [schemes, setSchemes] = useState<RandomizationScheme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSchemes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/randomization/schemes");
      if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);
      const data: RandomizationResponse = await res.json();
      setSchemes(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSchemes();
  }, [fetchSchemes]);

  // --- Computed stats ---
  const totalSchemes = schemes.length;
  const activeSchemes = schemes.filter((s) => s.status === "ACTIVE").length;
  const totalRandomized = schemes.reduce(
    (sum, s) => sum + s.arms.reduce((a, arm) => a + arm.current_count, 0),
    0
  );
  const doubleBlindCount = schemes.filter(
    (s) => s.blinding_level === "DOUBLE_BLIND"
  ).length;

  // --- Loading state ---
  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Randomization & Blinding</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage randomization schemes and blinding assignments
          </p>
        </div>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-muted-foreground">Loading randomization schemes...</span>
        </div>
      </div>
    );
  }

  // --- Error state ---
  if (error) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Randomization & Blinding</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage randomization schemes and blinding assignments
          </p>
        </div>
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertCircle className="h-8 w-8 text-destructive mb-3" />
              <p className="text-sm text-destructive font-medium">
                Failed to load randomization schemes
              </p>
              <p className="text-xs text-muted-foreground mt-1">{error}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={fetchSchemes}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Randomization & Blinding</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage randomization schemes and blinding assignments
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchSchemes}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Schemes</CardTitle>
            <Shuffle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalSchemes}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Schemes</CardTitle>
            <Target className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{activeSchemes}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Randomized</CardTitle>
            <Users className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{totalRandomized}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Double-Blind</CardTitle>
            <Lock className="h-4 w-4 text-indigo-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-indigo-600">{doubleBlindCount}</div>
          </CardContent>
        </Card>
      </div>

      {/* Scheme Cards */}
      {schemes.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="py-12 text-center text-muted-foreground">
              No randomization schemes found
            </div>
          </CardContent>
        </Card>
      ) : (
        schemes.map((scheme) => {
          const schemeTotal = scheme.arms.reduce((s, a) => s + a.current_count, 0);
          const schemeTarget = scheme.arms.reduce((s, a) => s + a.target_count, 0);

          return (
            <Card key={scheme.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">{scheme.trial_name}</CardTitle>
                    <CardDescription className="mt-1">
                      {schemeTotal} of {schemeTarget} subjects randomized
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={methodColors[scheme.method] || ""}>
                      {formatLabel(scheme.method)}
                    </Badge>
                    <Badge className={blindingColors[scheme.blinding_level] || ""}>
                      {blindingIcon(scheme.blinding_level)}
                      {formatLabel(scheme.blinding_level)}
                    </Badge>
                    <Badge className={statusColors[scheme.status] || ""}>
                      {formatLabel(scheme.status)}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Arm</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Enrolled / Target</TableHead>
                        <TableHead className="w-[200px]">Progress</TableHead>
                        <TableHead className="text-right">Weight</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {scheme.arms.map((arm) => {
                        const pct =
                          arm.target_count > 0
                            ? Math.round((arm.current_count / arm.target_count) * 100)
                            : 0;
                        return (
                          <TableRow key={arm.id}>
                            <TableCell>
                              <div>
                                <span className="font-medium">{arm.name}</span>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                  {arm.description}
                                </p>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge className={armTypeColors[arm.arm_type] || ""}>
                                {formatLabel(arm.arm_type)}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <span className="font-semibold">{arm.current_count}</span>
                              <span className="text-muted-foreground"> / {arm.target_count}</span>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Progress value={Math.min(100, pct)} className="h-2" />
                                <span className="text-xs text-muted-foreground w-10 text-right">
                                  {pct}%
                                </span>
                              </div>
                            </TableCell>
                            <TableCell className="text-right font-mono text-sm">
                              {arm.allocation_weight}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          );
        })
      )}
    </div>
  );
}
