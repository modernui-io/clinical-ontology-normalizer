"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Shield,
  Users,
  Key,
  Plus,
  Search,
  Settings,
  CheckCircle,
  XCircle,
  Crown,
  Lock,
  RefreshCw,
  AlertTriangle,
  Play,
  CircleCheck,
  Clock,
  Loader2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types mirroring backend schemas
// ---------------------------------------------------------------------------

interface ReviewCycle {
  id: string;
  name: string;
  cycle_type: "QUARTERLY" | "SEMI_ANNUAL" | "ANNUAL";
  status: "PLANNED" | "IN_PROGRESS" | "COMPLETED" | "OVERDUE";
  start_date: string;
  end_date: string;
  reviewer: string;
  created_at: string;
}

interface ReviewCycleListResponse {
  items: ReviewCycle[];
  total: number;
}

interface AccessEntitlement {
  id: string;
  user_id: string;
  user_name: string;
  user_role: string;
  resource: string;
  access_level: "READ" | "WRITE" | "ADMIN" | "OWNER";
  granted_date: string;
  granted_by: string;
  last_used: string | null;
  justification: string;
}

interface EntitlementListResponse {
  items: AccessEntitlement[];
  total: number;
}

interface ReviewDecision {
  id: string;
  cycle_id: string;
  entitlement_id: string;
  decision: "CERTIFY" | "REVOKE" | "MODIFY" | "ESCALATE";
  reviewer: string;
  decided_at: string;
  comments: string;
  new_access_level: string | null;
}

interface DecisionListResponse {
  items: ReviewDecision[];
  total: number;
}

interface AccessReviewMetrics {
  total_cycles: number;
  total_entitlements: number;
  certification_rate: number;
  revocation_rate: number;
  avg_review_time_days: number;
  overdue_reviews: number;
  by_decision: Record<string, number>;
  excessive_access_count: number;
}

interface ExcessiveAccessEntry {
  user_id: string;
  user_name: string;
  user_role: string;
  reasons: string[];
  entitlements: AccessEntitlement[];
}

interface ExcessiveAccessResponse {
  items: ExcessiveAccessEntry[];
  total: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const API_BASE = "/api/access-review";

const cycleStatusColor = (status: ReviewCycle["status"]): string => {
  switch (status) {
    case "PLANNED":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "IN_PROGRESS":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
    case "COMPLETED":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "OVERDUE":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const cycleTypeLabel = (ct: ReviewCycle["cycle_type"]): string => {
  switch (ct) {
    case "QUARTERLY":
      return "Quarterly";
    case "SEMI_ANNUAL":
      return "Semi-Annual";
    case "ANNUAL":
      return "Annual";
    default:
      return ct;
  }
};

const accessLevelColor = (level: AccessEntitlement["access_level"]): string => {
  switch (level) {
    case "OWNER":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "ADMIN":
      return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
    case "WRITE":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "READ":
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const decisionColor = (d: ReviewDecision["decision"]): string => {
  switch (d) {
    case "CERTIFY":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "REVOKE":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "MODIFY":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
    case "ESCALATE":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const formatDate = (dateString: string): string =>
  new Date(dateString).toLocaleDateString();

const formatDateTime = (dateString: string | null): string => {
  if (!dateString) return "Never";
  return new Date(dateString).toLocaleString();
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AccessControlPage() {
  // Data state
  const [cycles, setCycles] = useState<ReviewCycle[]>([]);
  const [entitlements, setEntitlements] = useState<AccessEntitlement[]>([]);
  const [decisions, setDecisions] = useState<ReviewDecision[]>([]);
  const [metrics, setMetrics] = useState<AccessReviewMetrics | null>(null);
  const [excessiveAccess, setExcessiveAccess] = useState<ExcessiveAccessEntry[]>([]);

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [entitlementSearch, setEntitlementSearch] = useState("");

  // Create cycle dialog state
  const [isCycleDialogOpen, setIsCycleDialogOpen] = useState(false);
  const [newCycleName, setNewCycleName] = useState("");
  const [newCycleType, setNewCycleType] = useState<"QUARTERLY" | "SEMI_ANNUAL" | "ANNUAL">("QUARTERLY");
  const [newCycleStartDate, setNewCycleStartDate] = useState("");
  const [newCycleEndDate, setNewCycleEndDate] = useState("");
  const [newCycleReviewer, setNewCycleReviewer] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // -------------------------------------------------------------------------
  // Data fetching
  // -------------------------------------------------------------------------

  const fetchAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [cyclesRes, entitlementsRes, decisionsRes, metricsRes, excessiveRes] =
        await Promise.all([
          fetch(`${API_BASE}/cycles`),
          fetch(`${API_BASE}/entitlements`),
          fetch(`${API_BASE}/decisions`),
          fetch(`${API_BASE}/metrics`),
          fetch(`${API_BASE}/excessive-access`),
        ]);

      // Check for HTTP errors on each response
      const responses = [cyclesRes, entitlementsRes, decisionsRes, metricsRes, excessiveRes];
      const labels = ["cycles", "entitlements", "decisions", "metrics", "excessive-access"];
      for (let i = 0; i < responses.length; i++) {
        if (!responses[i].ok) {
          throw new Error(
            `Failed to fetch ${labels[i]}: ${responses[i].status} ${responses[i].statusText}`
          );
        }
      }

      const cyclesData: ReviewCycleListResponse = await cyclesRes.json();
      const entitlementsData: EntitlementListResponse = await entitlementsRes.json();
      const decisionsData: DecisionListResponse = await decisionsRes.json();
      const metricsData: AccessReviewMetrics = await metricsRes.json();
      const excessiveData: ExcessiveAccessResponse = await excessiveRes.json();

      setCycles(cyclesData.items);
      setEntitlements(entitlementsData.items);
      setDecisions(decisionsData.items);
      setMetrics(metricsData);
      setExcessiveAccess(excessiveData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // -------------------------------------------------------------------------
  // Cycle lifecycle actions
  // -------------------------------------------------------------------------

  const handleStartCycle = async (cycleId: string) => {
    try {
      const res = await fetch(`${API_BASE}/cycles/${cycleId}/start`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to start cycle: ${res.status}`);
      }
      const updated: ReviewCycle = await res.json();
      setCycles((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to start cycle");
    }
  };

  const handleCompleteCycle = async (cycleId: string) => {
    try {
      const res = await fetch(`${API_BASE}/cycles/${cycleId}/complete`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to complete cycle: ${res.status}`);
      }
      const updated: ReviewCycle = await res.json();
      setCycles((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to complete cycle");
    }
  };

  const handleDeleteCycle = async (cycleId: string) => {
    try {
      const res = await fetch(`${API_BASE}/cycles/${cycleId}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to delete cycle: ${res.status}`);
      }
      setCycles((prev) => prev.filter((c) => c.id !== cycleId));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete cycle");
    }
  };

  // -------------------------------------------------------------------------
  // Create cycle
  // -------------------------------------------------------------------------

  const handleCreateCycle = async () => {
    if (!newCycleName || !newCycleStartDate || !newCycleEndDate || !newCycleReviewer) return;
    setIsCreating(true);
    try {
      const res = await fetch(`${API_BASE}/cycles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newCycleName,
          cycle_type: newCycleType,
          start_date: new Date(newCycleStartDate).toISOString(),
          end_date: new Date(newCycleEndDate).toISOString(),
          reviewer: newCycleReviewer,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to create cycle: ${res.status}`);
      }
      const created: ReviewCycle = await res.json();
      setCycles((prev) => [...prev, created]);
      setIsCycleDialogOpen(false);
      setNewCycleName("");
      setNewCycleType("QUARTERLY");
      setNewCycleStartDate("");
      setNewCycleEndDate("");
      setNewCycleReviewer("");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create cycle");
    } finally {
      setIsCreating(false);
    }
  };

  // -------------------------------------------------------------------------
  // Filtering
  // -------------------------------------------------------------------------

  const filteredCycles = cycles.filter(
    (c) =>
      searchQuery === "" ||
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.reviewer.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredEntitlements = entitlements.filter(
    (e) =>
      entitlementSearch === "" ||
      e.user_name.toLowerCase().includes(entitlementSearch.toLowerCase()) ||
      e.resource.toLowerCase().includes(entitlementSearch.toLowerCase()) ||
      e.user_role.toLowerCase().includes(entitlementSearch.toLowerCase())
  );

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading access review data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Error Loading Data
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button onClick={fetchAll} variant="outline">
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Shield className="h-6 w-6" />
            Access Control
          </h1>
          <p className="text-muted-foreground">
            Manage access review cycles, entitlements, and compliance
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchAll}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Stats from Metrics API */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Review Cycles</CardTitle>
            <Settings className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.total_cycles ?? 0}</div>
            <p className="text-xs text-muted-foreground">
              {metrics?.overdue_reviews ?? 0} overdue
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Entitlements</CardTitle>
            <Key className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.total_entitlements ?? 0}</div>
            <p className="text-xs text-muted-foreground">
              {((metrics?.certification_rate ?? 0) * 100).toFixed(1)}% certified
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Avg Review Time</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(metrics?.avg_review_time_days ?? 0).toFixed(1)}d
            </div>
            <p className="text-xs text-muted-foreground">
              {((metrics?.revocation_rate ?? 0) * 100).toFixed(1)}% revoked
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Excessive Access</CardTitle>
            <Crown className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.excessive_access_count ?? 0}</div>
            <p className="text-xs text-muted-foreground">Users flagged</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="cycles" className="space-y-4">
        <TabsList>
          <TabsTrigger value="cycles" className="gap-2">
            <Settings className="h-4 w-4" />
            Review Cycles
          </TabsTrigger>
          <TabsTrigger value="entitlements" className="gap-2">
            <Key className="h-4 w-4" />
            Entitlements
          </TabsTrigger>
          <TabsTrigger value="decisions" className="gap-2">
            <CheckCircle className="h-4 w-4" />
            Decisions
          </TabsTrigger>
          <TabsTrigger value="excessive" className="gap-2">
            <AlertTriangle className="h-4 w-4" />
            Excessive Access
          </TabsTrigger>
        </TabsList>

        {/* Review Cycles Tab */}
        <TabsContent value="cycles" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Review Cycles</CardTitle>
                  <CardDescription>
                    Manage periodic access review cycles and their lifecycle
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search cycles..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-8 w-[200px]"
                    />
                  </div>
                  <Dialog open={isCycleDialogOpen} onOpenChange={setIsCycleDialogOpen}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <Plus className="mr-2 h-4 w-4" />
                        New Cycle
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create Review Cycle</DialogTitle>
                        <DialogDescription>
                          Define a new periodic access review cycle
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="cycle-name">Cycle Name</Label>
                          <Input
                            id="cycle-name"
                            placeholder="Q1 2026 Access Review"
                            value={newCycleName}
                            onChange={(e) => setNewCycleName(e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="cycle-type">Cycle Type</Label>
                          <select
                            id="cycle-type"
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
                            value={newCycleType}
                            onChange={(e) =>
                              setNewCycleType(e.target.value as "QUARTERLY" | "SEMI_ANNUAL" | "ANNUAL")
                            }
                          >
                            <option value="QUARTERLY">Quarterly</option>
                            <option value="SEMI_ANNUAL">Semi-Annual</option>
                            <option value="ANNUAL">Annual</option>
                          </select>
                        </div>
                        <div className="grid gap-4 md:grid-cols-2">
                          <div className="space-y-2">
                            <Label htmlFor="cycle-start">Start Date</Label>
                            <Input
                              id="cycle-start"
                              type="date"
                              value={newCycleStartDate}
                              onChange={(e) => setNewCycleStartDate(e.target.value)}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="cycle-end">End Date</Label>
                            <Input
                              id="cycle-end"
                              type="date"
                              value={newCycleEndDate}
                              onChange={(e) => setNewCycleEndDate(e.target.value)}
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="cycle-reviewer">Reviewer</Label>
                          <Input
                            id="cycle-reviewer"
                            placeholder="Reviewer name"
                            value={newCycleReviewer}
                            onChange={(e) => setNewCycleReviewer(e.target.value)}
                          />
                        </div>
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setIsCycleDialogOpen(false)}
                        >
                          Cancel
                        </Button>
                        <Button onClick={handleCreateCycle} disabled={isCreating}>
                          {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                          Create Cycle
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {filteredCycles.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No review cycles found.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Cycle</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Reviewer</TableHead>
                      <TableHead>Start</TableHead>
                      <TableHead>End</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredCycles.map((cycle) => (
                      <TableRow key={cycle.id}>
                        <TableCell>
                          <div className="font-medium">{cycle.name}</div>
                          <div className="text-xs text-muted-foreground">{cycle.id}</div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">
                            {cycleTypeLabel(cycle.cycle_type)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={cycleStatusColor(cycle.status)}>
                            {cycle.status === "COMPLETED" && <CircleCheck className="mr-1 h-3 w-3" />}
                            {cycle.status === "OVERDUE" && <AlertTriangle className="mr-1 h-3 w-3" />}
                            {cycle.status === "IN_PROGRESS" && <Play className="mr-1 h-3 w-3" />}
                            {cycle.status === "PLANNED" && <Clock className="mr-1 h-3 w-3" />}
                            {cycle.status.replace("_", " ")}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">{cycle.reviewer}</TableCell>
                        <TableCell className="text-sm">{formatDate(cycle.start_date)}</TableCell>
                        <TableCell className="text-sm">{formatDate(cycle.end_date)}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {cycle.status === "PLANNED" && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleStartCycle(cycle.id)}
                                title="Start cycle"
                              >
                                <Play className="h-4 w-4" />
                              </Button>
                            )}
                            {cycle.status === "IN_PROGRESS" && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleCompleteCycle(cycle.id)}
                                title="Complete cycle"
                              >
                                <CircleCheck className="h-4 w-4" />
                              </Button>
                            )}
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeleteCycle(cycle.id)}
                              title="Delete cycle"
                            >
                              <XCircle className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Entitlements Tab */}
        <TabsContent value="entitlements" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Access Entitlements</CardTitle>
                  <CardDescription>
                    All access grants linking users to resources
                  </CardDescription>
                </div>
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search entitlements..."
                    value={entitlementSearch}
                    onChange={(e) => setEntitlementSearch(e.target.value)}
                    className="pl-8 w-[200px]"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {filteredEntitlements.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No entitlements found.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Resource</TableHead>
                      <TableHead>Access Level</TableHead>
                      <TableHead>Granted By</TableHead>
                      <TableHead>Granted</TableHead>
                      <TableHead>Last Used</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredEntitlements.map((ent) => (
                      <TableRow key={ent.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{ent.user_name}</div>
                            <div className="text-xs text-muted-foreground">{ent.user_id}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{ent.user_role}</Badge>
                        </TableCell>
                        <TableCell>
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            {ent.resource}
                          </code>
                        </TableCell>
                        <TableCell>
                          <Badge className={accessLevelColor(ent.access_level)}>
                            {ent.access_level === "ADMIN" && <Crown className="mr-1 h-3 w-3" />}
                            {ent.access_level === "OWNER" && <Lock className="mr-1 h-3 w-3" />}
                            {ent.access_level}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">{ent.granted_by}</TableCell>
                        <TableCell className="text-sm">{formatDate(ent.granted_date)}</TableCell>
                        <TableCell className="text-sm">{formatDateTime(ent.last_used)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Decisions Tab */}
        <TabsContent value="decisions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Review Decisions</CardTitle>
              <CardDescription>
                All review decisions made across cycles
              </CardDescription>
            </CardHeader>
            <CardContent>
              {decisions.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No decisions recorded yet.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Decision</TableHead>
                      <TableHead>Cycle</TableHead>
                      <TableHead>Entitlement</TableHead>
                      <TableHead>Reviewer</TableHead>
                      <TableHead>Decided At</TableHead>
                      <TableHead>Comments</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {decisions.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell>
                          <Badge className={decisionColor(d.decision)}>
                            {d.decision === "CERTIFY" && <CheckCircle className="mr-1 h-3 w-3" />}
                            {d.decision === "REVOKE" && <XCircle className="mr-1 h-3 w-3" />}
                            {d.decision === "ESCALATE" && <AlertTriangle className="mr-1 h-3 w-3" />}
                            {d.decision}
                          </Badge>
                          {d.new_access_level && (
                            <span className="ml-2 text-xs text-muted-foreground">
                              New level: {d.new_access_level}
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            {d.cycle_id}
                          </code>
                        </TableCell>
                        <TableCell>
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            {d.entitlement_id}
                          </code>
                        </TableCell>
                        <TableCell className="text-sm">{d.reviewer}</TableCell>
                        <TableCell className="text-sm">{formatDateTime(d.decided_at)}</TableCell>
                        <TableCell className="text-sm max-w-[200px] truncate">
                          {d.comments || "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Excessive Access Tab */}
        <TabsContent value="excessive" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                Excessive Access Report
              </CardTitle>
              <CardDescription>
                Users flagged for ADMIN on 3+ resources or unused access exceeding 90 days
              </CardDescription>
            </CardHeader>
            <CardContent>
              {excessiveAccess.length === 0 ? (
                <div className="text-center py-8 space-y-2">
                  <CheckCircle className="h-8 w-8 text-green-500 mx-auto" />
                  <p className="text-sm text-muted-foreground">
                    No users flagged for excessive access.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {excessiveAccess.map((entry) => (
                    <div
                      key={entry.user_id}
                      className="border rounded-lg p-4 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Users className="h-5 w-5 text-muted-foreground" />
                          <div>
                            <div className="font-medium">{entry.user_name}</div>
                            <div className="text-xs text-muted-foreground">
                              {entry.user_id} - {entry.user_role}
                            </div>
                          </div>
                        </div>
                        <Badge variant="destructive">
                          {entry.reasons.length} flag{entry.reasons.length !== 1 ? "s" : ""}
                        </Badge>
                      </div>
                      <div className="space-y-1">
                        {entry.reasons.map((reason, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-300">
                            <AlertTriangle className="h-3 w-3 flex-shrink-0" />
                            {reason}
                          </div>
                        ))}
                      </div>
                      {entry.entitlements.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {entry.entitlements.map((ent) => (
                            <Badge
                              key={ent.id}
                              className={accessLevelColor(ent.access_level)}
                            >
                              {ent.resource}: {ent.access_level}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
