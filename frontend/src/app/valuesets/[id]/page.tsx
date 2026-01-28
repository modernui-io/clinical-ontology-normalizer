"use client";

import { useState, useCallback, useEffect, Suspense } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ArrowLeft,
  Plus,
  Trash2,
  RefreshCw,
  Download,
  List,
  GitBranch,
  CheckCircle,
  Archive,
  History,
  Search,
  Edit,
  Save,
  X,
  Play,
  FileJson,
  FileSpreadsheet,
  AlertCircle,
} from "lucide-react";

// Types
interface ValueSetCode {
  system: string;
  code: string;
  display: string;
  version: string | null;
  inactive: boolean;
  abstract: boolean;
}

interface InclusionRule {
  rule_type: string;
  system: string;
  code: string | null;
  filter_property: string | null;
  filter_operator: string | null;
  filter_value: string | null;
  value_set_id: string | null;
  include: boolean;
}

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

interface ExpansionResponse {
  value_set_id: string;
  value_set_url: string | null;
  timestamp: string;
  total: number;
  offset: number;
  codes: ValueSetCode[];
}

interface VersionHistoryItem {
  version_id: string;
  version: string;
  status: string;
  created_at: string;
  created_by: string | null;
  notes: string | null;
  code_count: number;
}

interface ValidationResponse {
  valid: boolean;
  message: string | null;
  display: string | null;
  code: string | null;
  system: string | null;
}

// API
const API_BASE = "/api/valuesets";

async function fetchValueSet(id: string): Promise<ValueSet> {
  const response = await fetch(`${API_BASE}/${id}`);
  if (!response.ok) throw new Error("Failed to fetch value set");
  return response.json();
}

async function expandValueSet(
  id: string,
  params: { filter?: string; offset?: number; count?: number }
): Promise<ExpansionResponse> {
  const searchParams = new URLSearchParams();
  if (params.filter) searchParams.set("filter", params.filter);
  if (params.offset) searchParams.set("offset", String(params.offset));
  if (params.count) searchParams.set("count", String(params.count));

  const response = await fetch(`${API_BASE}/${id}/expand?${searchParams.toString()}`);
  if (!response.ok) throw new Error("Failed to expand value set");
  return response.json();
}

async function fetchVersionHistory(id: string): Promise<{ versions: VersionHistoryItem[] }> {
  const response = await fetch(`${API_BASE}/${id}/versions`);
  if (!response.ok) throw new Error("Failed to fetch version history");
  return response.json();
}

async function addCode(id: string, code: Partial<ValueSetCode>): Promise<ValueSet> {
  const response = await fetch(`${API_BASE}/${id}/codes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(code),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to add code");
  }
  return response.json();
}

async function removeCode(id: string, system: string, code: string): Promise<ValueSet> {
  const response = await fetch(
    `${API_BASE}/${id}/codes?system=${encodeURIComponent(system)}&code=${encodeURIComponent(code)}`,
    { method: "DELETE" }
  );
  if (!response.ok) throw new Error("Failed to remove code");
  return response.json();
}

async function addRule(id: string, rule: Partial<InclusionRule>): Promise<ValueSet> {
  const response = await fetch(`${API_BASE}/${id}/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rule),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to add rule");
  }
  return response.json();
}

async function removeRule(id: string, ruleIndex: number): Promise<ValueSet> {
  const response = await fetch(`${API_BASE}/${id}/rules/${ruleIndex}`, { method: "DELETE" });
  if (!response.ok) throw new Error("Failed to remove rule");
  return response.json();
}

async function activateValueSet(id: string): Promise<ValueSet> {
  const response = await fetch(`${API_BASE}/${id}/activate`, { method: "POST" });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to activate");
  }
  return response.json();
}

async function retireValueSet(id: string): Promise<ValueSet> {
  const response = await fetch(`${API_BASE}/${id}/retire`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to retire");
  return response.json();
}

async function validateCode(
  id: string,
  system: string,
  code: string
): Promise<ValidationResponse> {
  const response = await fetch(
    `${API_BASE}/${id}/validate?system=${encodeURIComponent(system)}&code=${encodeURIComponent(code)}`
  );
  if (!response.ok) throw new Error("Failed to validate");
  return response.json();
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

const RULE_TYPE_LABELS: Record<string, string> = {
  code: "Include Code",
  filter: "Filter",
  descendants: "All Descendants",
  ancestors: "All Ancestors",
  value_set: "From Value Set",
};

function ValueSetDetailContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const id = params.id as string;
  const initialTab = searchParams.get("tab") || "codes";

  const [activeTab, setActiveTab] = useState(initialTab);
  const [expandFilter, setExpandFilter] = useState("");
  const [expandOffset, setExpandOffset] = useState(0);
  const [expandCount] = useState(100);

  // Validation state
  const [validateSystem, setValidateSystem] = useState("");
  const [validateCodeInput, setValidateCodeInput] = useState("");
  const [validationResult, setValidationResult] = useState<ValidationResponse | null>(null);

  // Add code dialog
  const [isAddCodeOpen, setIsAddCodeOpen] = useState(false);
  const [newCode, setNewCode] = useState({ system: "", code: "", display: "" });

  // Add rule dialog
  const [isAddRuleOpen, setIsAddRuleOpen] = useState(false);
  const [newRule, setNewRule] = useState({
    rule_type: "code",
    system: "",
    code: "",
    filter_property: "",
    filter_operator: "=",
    filter_value: "",
    include: true,
  });

  // Fetch value set
  const {
    data: valueSet,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["valueset", id],
    queryFn: () => fetchValueSet(id),
  });

  // Fetch expansion
  const {
    data: expansion,
    isLoading: isExpanding,
    refetch: refetchExpansion,
  } = useQuery({
    queryKey: ["valueset-expansion", id, expandFilter, expandOffset, expandCount],
    queryFn: () =>
      expandValueSet(id, { filter: expandFilter || undefined, offset: expandOffset, count: expandCount }),
    enabled: activeTab === "codes" || activeTab === "expand",
  });

  // Fetch version history
  const { data: historyData } = useQuery({
    queryKey: ["valueset-history", id],
    queryFn: () => fetchVersionHistory(id),
    enabled: activeTab === "history",
  });

  // Mutations
  const addCodeMutation = useMutation({
    mutationFn: (code: Partial<ValueSetCode>) => addCode(id, code),
    onSuccess: () => {
      toast.success("Code added successfully");
      queryClient.invalidateQueries({ queryKey: ["valueset", id] });
      queryClient.invalidateQueries({ queryKey: ["valueset-expansion", id] });
      setIsAddCodeOpen(false);
      setNewCode({ system: "", code: "", display: "" });
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const removeCodeMutation = useMutation({
    mutationFn: ({ system, code }: { system: string; code: string }) => removeCode(id, system, code),
    onSuccess: () => {
      toast.success("Code removed successfully");
      queryClient.invalidateQueries({ queryKey: ["valueset", id] });
      queryClient.invalidateQueries({ queryKey: ["valueset-expansion", id] });
    },
    onError: () => {
      toast.error("Failed to remove code");
    },
  });

  const addRuleMutation = useMutation({
    mutationFn: (rule: Partial<InclusionRule>) => addRule(id, rule),
    onSuccess: () => {
      toast.success("Rule added successfully");
      queryClient.invalidateQueries({ queryKey: ["valueset", id] });
      queryClient.invalidateQueries({ queryKey: ["valueset-expansion", id] });
      setIsAddRuleOpen(false);
      setNewRule({
        rule_type: "code",
        system: "",
        code: "",
        filter_property: "",
        filter_operator: "=",
        filter_value: "",
        include: true,
      });
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const removeRuleMutation = useMutation({
    mutationFn: (ruleIndex: number) => removeRule(id, ruleIndex),
    onSuccess: () => {
      toast.success("Rule removed successfully");
      queryClient.invalidateQueries({ queryKey: ["valueset", id] });
      queryClient.invalidateQueries({ queryKey: ["valueset-expansion", id] });
    },
    onError: () => {
      toast.error("Failed to remove rule");
    },
  });

  const activateMutation = useMutation({
    mutationFn: () => activateValueSet(id),
    onSuccess: () => {
      toast.success("Value set activated");
      queryClient.invalidateQueries({ queryKey: ["valueset", id] });
      queryClient.invalidateQueries({ queryKey: ["valueset-history", id] });
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const retireMutation = useMutation({
    mutationFn: () => retireValueSet(id),
    onSuccess: () => {
      toast.success("Value set retired");
      queryClient.invalidateQueries({ queryKey: ["valueset", id] });
      queryClient.invalidateQueries({ queryKey: ["valueset-history", id] });
    },
    onError: () => {
      toast.error("Failed to retire value set");
    },
  });

  // Handlers
  const handleValidate = useCallback(async () => {
    if (!validateSystem || !validateCodeInput) {
      toast.error("Please enter both system and code");
      return;
    }
    try {
      const result = await validateCode(id, validateSystem, validateCodeInput);
      setValidationResult(result);
    } catch {
      toast.error("Validation failed");
    }
  }, [id, validateSystem, validateCodeInput]);

  const handleExport = useCallback((format: "fhir" | "csv") => {
    window.open(`${API_BASE}/${id}/export?format=${format}`, "_blank");
  }, [id]);

  // Update tab from URL
  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab) setActiveTab(tab);
  }, [searchParams]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
      </div>
    );
  }

  if (error || !valueSet) {
    return (
      <div className="p-6">
        <div className="rounded-lg bg-red-50 p-4 text-red-800 dark:bg-red-900/20 dark:text-red-200">
          <AlertCircle className="inline mr-2 h-4 w-4" />
          Failed to load value set. It may not exist or the backend is unavailable.
        </div>
        <Link href="/valuesets">
          <Button className="mt-4" variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Value Sets
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/valuesets">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {valueSet.title || valueSet.name}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <Badge className={TYPE_COLORS[valueSet.value_set_type]}>
                {valueSet.value_set_type === "extensional" ? (
                  <List className="mr-1 h-3 w-3" />
                ) : (
                  <GitBranch className="mr-1 h-3 w-3" />
                )}
                {valueSet.value_set_type}
              </Badge>
              <Badge className={STATUS_COLORS[valueSet.status]}>
                {valueSet.status.toUpperCase()}
              </Badge>
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">v{valueSet.version}</code>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {valueSet.status === "draft" && (
            <Button
              variant="outline"
              onClick={() => activateMutation.mutate()}
              disabled={activateMutation.isPending}
            >
              <CheckCircle className="mr-2 h-4 w-4" />
              Activate
            </Button>
          )}
          {valueSet.status === "active" && (
            <Button
              variant="outline"
              onClick={() => retireMutation.mutate()}
              disabled={retireMutation.isPending}
            >
              <Archive className="mr-2 h-4 w-4" />
              Retire
            </Button>
          )}
          <Button variant="outline" onClick={() => handleExport("fhir")}>
            <FileJson className="mr-2 h-4 w-4" />
            Export FHIR
          </Button>
          <Button variant="outline" onClick={() => handleExport("csv")}>
            <FileSpreadsheet className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Description */}
      {valueSet.description && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-muted-foreground">{valueSet.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Info Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Codes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{expansion?.total || valueSet.code_count}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Rules</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{valueSet.rule_count}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Created</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm">{new Date(valueSet.created_at).toLocaleDateString()}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Updated</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm">{new Date(valueSet.updated_at).toLocaleDateString()}</div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="codes" className="gap-2">
            <List className="h-4 w-4" />
            Codes
          </TabsTrigger>
          {valueSet.value_set_type === "intensional" && (
            <TabsTrigger value="rules" className="gap-2">
              <GitBranch className="h-4 w-4" />
              Rules
            </TabsTrigger>
          )}
          <TabsTrigger value="validate" className="gap-2">
            <CheckCircle className="h-4 w-4" />
            Validate
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-2">
            <History className="h-4 w-4" />
            History
          </TabsTrigger>
        </TabsList>

        {/* Codes Tab */}
        <TabsContent value="codes" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Expanded Codes</CardTitle>
                  <CardDescription>
                    {isExpanding ? "Expanding..." : `${expansion?.total || 0} codes in this value set`}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Filter codes..."
                      value={expandFilter}
                      onChange={(e) => {
                        setExpandFilter(e.target.value);
                        setExpandOffset(0);
                      }}
                      className="pl-8 w-[200px]"
                    />
                  </div>
                  <Button variant="outline" size="sm" onClick={() => refetchExpansion()}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Refresh
                  </Button>
                  {valueSet.value_set_type === "extensional" && valueSet.status === "draft" && (
                    <Dialog open={isAddCodeOpen} onOpenChange={setIsAddCodeOpen}>
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <Plus className="mr-2 h-4 w-4" />
                          Add Code
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Add Code</DialogTitle>
                          <DialogDescription>
                            Add a new code to this value set.
                          </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                          <div className="grid gap-2">
                            <Label htmlFor="system">System</Label>
                            <Input
                              id="system"
                              placeholder="http://snomed.info/sct"
                              value={newCode.system}
                              onChange={(e) => setNewCode({ ...newCode, system: e.target.value })}
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label htmlFor="code">Code</Label>
                            <Input
                              id="code"
                              placeholder="73211009"
                              value={newCode.code}
                              onChange={(e) => setNewCode({ ...newCode, code: e.target.value })}
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label htmlFor="display">Display</Label>
                            <Input
                              id="display"
                              placeholder="Diabetes mellitus"
                              value={newCode.display}
                              onChange={(e) => setNewCode({ ...newCode, display: e.target.value })}
                            />
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setIsAddCodeOpen(false)}>
                            Cancel
                          </Button>
                          <Button
                            onClick={() => addCodeMutation.mutate(newCode)}
                            disabled={!newCode.system || !newCode.code || addCodeMutation.isPending}
                          >
                            Add Code
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {isExpanding ? (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
                </div>
              ) : !expansion?.codes.length ? (
                <div className="py-12 text-center text-zinc-500">
                  <List className="mx-auto h-12 w-12 text-muted-foreground/50" />
                  <p className="mt-4">No codes found.</p>
                </div>
              ) : (
                <>
                  <div className="rounded-lg border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>System</TableHead>
                          <TableHead>Code</TableHead>
                          <TableHead>Display</TableHead>
                          <TableHead>Status</TableHead>
                          {valueSet.value_set_type === "extensional" && valueSet.status === "draft" && (
                            <TableHead className="text-right">Actions</TableHead>
                          )}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {expansion.codes.map((code, idx) => (
                          <TableRow key={`${code.system}-${code.code}-${idx}`}>
                            <TableCell>
                              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                {code.system.split("/").pop()}
                              </code>
                            </TableCell>
                            <TableCell className="font-mono">{code.code}</TableCell>
                            <TableCell>{code.display}</TableCell>
                            <TableCell>
                              {code.inactive && (
                                <Badge variant="outline" className="text-gray-500">
                                  Inactive
                                </Badge>
                              )}
                              {code.abstract && (
                                <Badge variant="outline" className="text-purple-500">
                                  Abstract
                                </Badge>
                              )}
                            </TableCell>
                            {valueSet.value_set_type === "extensional" && valueSet.status === "draft" && (
                              <TableCell className="text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-red-600"
                                  onClick={() =>
                                    removeCodeMutation.mutate({ system: code.system, code: code.code })
                                  }
                                  disabled={removeCodeMutation.isPending}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            )}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Pagination */}
                  {expansion.total > expandCount && (
                    <div className="mt-4 flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">
                        Showing {expandOffset + 1} to {Math.min(expandOffset + expandCount, expansion.total)} of{" "}
                        {expansion.total}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={expandOffset === 0}
                          onClick={() => setExpandOffset(Math.max(0, expandOffset - expandCount))}
                        >
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={expandOffset + expandCount >= expansion.total}
                          onClick={() => setExpandOffset(expandOffset + expandCount)}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Rules Tab (Intensional only) */}
        {valueSet.value_set_type === "intensional" && (
          <TabsContent value="rules" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Inclusion Rules</CardTitle>
                    <CardDescription>
                      Rules that define which codes are included in this value set
                    </CardDescription>
                  </div>
                  {valueSet.status === "draft" && (
                    <Dialog open={isAddRuleOpen} onOpenChange={setIsAddRuleOpen}>
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <Plus className="mr-2 h-4 w-4" />
                          Add Rule
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-lg">
                        <DialogHeader>
                          <DialogTitle>Add Inclusion Rule</DialogTitle>
                          <DialogDescription>
                            Define a rule to include or exclude codes.
                          </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                          <div className="grid gap-2">
                            <Label htmlFor="ruleType">Rule Type</Label>
                            <select
                              id="ruleType"
                              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                              value={newRule.rule_type}
                              onChange={(e) => setNewRule({ ...newRule, rule_type: e.target.value })}
                            >
                              <option value="code">Include Specific Code</option>
                              <option value="descendants">All Descendants</option>
                              <option value="ancestors">All Ancestors</option>
                              <option value="filter">Filter by Property</option>
                            </select>
                          </div>
                          <div className="grid gap-2">
                            <Label htmlFor="ruleSystem">Code System</Label>
                            <Input
                              id="ruleSystem"
                              placeholder="http://snomed.info/sct"
                              value={newRule.system}
                              onChange={(e) => setNewRule({ ...newRule, system: e.target.value })}
                            />
                          </div>
                          {(newRule.rule_type === "code" ||
                            newRule.rule_type === "descendants" ||
                            newRule.rule_type === "ancestors") && (
                            <div className="grid gap-2">
                              <Label htmlFor="ruleCode">Code</Label>
                              <Input
                                id="ruleCode"
                                placeholder="73211009"
                                value={newRule.code}
                                onChange={(e) => setNewRule({ ...newRule, code: e.target.value })}
                              />
                            </div>
                          )}
                          {newRule.rule_type === "filter" && (
                            <>
                              <div className="grid gap-2">
                                <Label htmlFor="filterProperty">Property</Label>
                                <Input
                                  id="filterProperty"
                                  placeholder="concept"
                                  value={newRule.filter_property}
                                  onChange={(e) =>
                                    setNewRule({ ...newRule, filter_property: e.target.value })
                                  }
                                />
                              </div>
                              <div className="grid gap-2">
                                <Label htmlFor="filterOperator">Operator</Label>
                                <select
                                  id="filterOperator"
                                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                  value={newRule.filter_operator}
                                  onChange={(e) =>
                                    setNewRule({ ...newRule, filter_operator: e.target.value })
                                  }
                                >
                                  <option value="=">=</option>
                                  <option value="is-a">is-a</option>
                                  <option value="descendent-of">descendent-of</option>
                                  <option value="is-not-a">is-not-a</option>
                                  <option value="regex">regex</option>
                                  <option value="in">in</option>
                                  <option value="not-in">not-in</option>
                                </select>
                              </div>
                              <div className="grid gap-2">
                                <Label htmlFor="filterValue">Value</Label>
                                <Input
                                  id="filterValue"
                                  value={newRule.filter_value}
                                  onChange={(e) => setNewRule({ ...newRule, filter_value: e.target.value })}
                                />
                              </div>
                            </>
                          )}
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              id="include"
                              checked={newRule.include}
                              onChange={(e) => setNewRule({ ...newRule, include: e.target.checked })}
                              className="h-4 w-4 rounded border-gray-300"
                            />
                            <Label htmlFor="include">Include (uncheck to exclude)</Label>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setIsAddRuleOpen(false)}>
                            Cancel
                          </Button>
                          <Button
                            onClick={() => addRuleMutation.mutate(newRule)}
                            disabled={!newRule.system || addRuleMutation.isPending}
                          >
                            Add Rule
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {valueSet.rule_count === 0 ? (
                  <div className="py-12 text-center text-zinc-500">
                    <GitBranch className="mx-auto h-12 w-12 text-muted-foreground/50" />
                    <p className="mt-4">No rules defined yet.</p>
                    <p className="text-sm mt-2">Add rules to define which codes should be included.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <p className="text-muted-foreground text-sm">
                      This value set has {valueSet.rule_count} rule(s). Rules are evaluated when the
                      value set is expanded.
                    </p>
                    <Button variant="outline" onClick={() => refetchExpansion()}>
                      <Play className="mr-2 h-4 w-4" />
                      Preview Expansion
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Validate Tab */}
        <TabsContent value="validate" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Validate Code</CardTitle>
              <CardDescription>
                Check if a code is included in this value set
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 max-w-md">
                <div className="grid gap-2">
                  <Label htmlFor="validateSystem">Code System</Label>
                  <Input
                    id="validateSystem"
                    placeholder="http://snomed.info/sct"
                    value={validateSystem}
                    onChange={(e) => setValidateSystem(e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="validateCode">Code</Label>
                  <Input
                    id="validateCode"
                    placeholder="73211009"
                    value={validateCodeInput}
                    onChange={(e) => setValidateCodeInput(e.target.value)}
                  />
                </div>
                <Button onClick={handleValidate} disabled={!validateSystem || !validateCodeInput}>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Validate
                </Button>

                {validationResult && (
                  <div
                    className={`p-4 rounded-lg ${
                      validationResult.valid
                        ? "bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-200"
                        : "bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-200"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {validationResult.valid ? (
                        <CheckCircle className="h-5 w-5" />
                      ) : (
                        <X className="h-5 w-5" />
                      )}
                      <span className="font-medium">
                        {validationResult.valid ? "Valid" : "Invalid"}
                      </span>
                    </div>
                    {validationResult.message && (
                      <p className="mt-2 text-sm">{validationResult.message}</p>
                    )}
                    {validationResult.display && (
                      <p className="mt-1 text-sm">Display: {validationResult.display}</p>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Version History</CardTitle>
              <CardDescription>
                Track changes to this value set over time
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!historyData?.versions.length ? (
                <div className="py-12 text-center text-zinc-500">
                  <History className="mx-auto h-12 w-12 text-muted-foreground/50" />
                  <p className="mt-4">No version history available.</p>
                </div>
              ) : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Version</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>By</TableHead>
                        <TableHead>Codes</TableHead>
                        <TableHead>Notes</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {historyData.versions.map((v) => (
                        <TableRow key={v.version_id}>
                          <TableCell>
                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                              v{v.version}
                            </code>
                          </TableCell>
                          <TableCell>
                            <Badge className={STATUS_COLORS[v.status]}>{v.status.toUpperCase()}</Badge>
                          </TableCell>
                          <TableCell>{new Date(v.created_at).toLocaleString()}</TableCell>
                          <TableCell>{v.created_by || "-"}</TableCell>
                          <TableCell>{v.code_count}</TableCell>
                          <TableCell className="max-w-[200px] truncate">{v.notes || "-"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function ValueSetDetailPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading Value Set...</div>}>
      <ValueSetDetailContent />
    </Suspense>
  );
}
