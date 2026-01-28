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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Shield,
  Plus,
  Search,
  RefreshCw,
  Loader2,
  AlertCircle,
  FileText,
  CheckCircle,
  Clock,
  Archive,
  XCircle,
  Link2,
  Eye,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface PolicySummary {
  id: string;
  name: string;
  description: string | null;
  source_organization: string | null;
  version: string | null;
  status: string;
  uploaded_at: string | null;
}

interface PolicySection {
  id: string;
  section_number: string;
  title: string;
  content_text: string;
  keywords: string[];
  applies_to_conditions: string[] | null;
  has_embedding: boolean;
}

interface PolicyDetail {
  id: string;
  name: string;
  description: string | null;
  source_organization: string | null;
  version: string | null;
  effective_date: string | null;
  status: string;
  content_hash: string;
  uploaded_at: string | null;
  sections: PolicySection[];
}

interface PolicyRuleMapping {
  id: string;
  policy_section_id: string;
  alert_rule_id: string;
  mapping_confidence: number;
  mapping_rationale: string;
}

interface SearchResult {
  section_id: string;
  policy_id: string;
  policy_name: string;
  section_title: string;
  content_text: string;
  relevance_score: number;
}

// =============================================================================
// Status Badge
// =============================================================================

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { icon: React.ReactNode; className: string }> = {
    draft: {
      icon: <Clock className="h-3 w-3" />,
      className:
        "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300",
    },
    active: {
      icon: <CheckCircle className="h-3 w-3" />,
      className:
        "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300",
    },
    superseded: {
      icon: <Archive className="h-3 w-3" />,
      className:
        "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300",
    },
    retired: {
      icon: <XCircle className="h-3 w-3" />,
      className:
        "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300",
    },
  };

  const cfg = config[status] || config.draft;

  return (
    <Badge variant="outline" className={`text-xs gap-1 ${cfg.className}`}>
      {cfg.icon}
      {status}
    </Badge>
  );
}

// =============================================================================
// Upload Policy Dialog
// =============================================================================

function UploadPolicyDialog({ onUploaded }: { onUploaded: () => void }) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [form, setForm] = useState({
    name: "",
    content_text: "",
    source_organization: "",
    version: "",
    description: "",
  });

  const handleUpload = async () => {
    if (!form.name || !form.content_text) return;
    setUploading(true);
    try {
      const res = await fetch("/api/policies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          content_text: form.content_text,
          source_organization: form.source_organization || undefined,
          version: form.version || undefined,
          description: form.description || undefined,
        }),
      });
      if (res.ok) {
        setForm({ name: "", content_text: "", source_organization: "", version: "", description: "" });
        setOpen(false);
        onUploaded();
      }
    } catch {
      // ignore
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="gap-2">
          <Plus className="h-4 w-4" />
          Upload Policy
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Upload New Policy
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="policy-name">Policy Name *</Label>
              <Input
                id="policy-name"
                placeholder="e.g., Diabetes Management Protocol v2"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="policy-version">Version</Label>
              <Input
                id="policy-version"
                placeholder="e.g., 2.0"
                value={form.version}
                onChange={(e) => setForm({ ...form, version: e.target.value })}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="policy-org">Source Organization</Label>
            <Input
              id="policy-org"
              placeholder="e.g., Internal Medicine Department"
              value={form.source_organization}
              onChange={(e) => setForm({ ...form, source_organization: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="policy-desc">Description</Label>
            <Input
              id="policy-desc"
              placeholder="Brief description of the policy"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="policy-content">Policy Content *</Label>
            <Textarea
              id="policy-content"
              placeholder="Paste the full policy text here. Sections will be automatically parsed..."
              value={form.content_text}
              onChange={(e) => setForm({ ...form, content_text: e.target.value })}
              rows={12}
              className="font-mono text-sm"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={uploading || !form.name || !form.content_text}
              className="gap-2"
            >
              {uploading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Upload
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Policy Detail Dialog
// =============================================================================

function PolicyDetailDialog({ policyId }: { policyId: string }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<PolicyDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [mappings, setMappings] = useState<PolicyRuleMapping[]>([]);
  const [linking, setLinking] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const loadDetail = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/policies/${policyId}`);
      if (res.ok) {
        const data = await res.json();
        setDetail(data);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const loadMappings = async () => {
    try {
      const res = await fetch(`/api/policies/${policyId}/rules`);
      if (res.ok) {
        const data = await res.json();
        setMappings(data.mappings || []);
      }
    } catch {
      // ignore
    }
  };

  const handleLinkRules = async () => {
    setLinking(true);
    try {
      const res = await fetch(`/api/policies/${policyId}/link-rules`, {
        method: "POST",
      });
      if (res.ok) {
        await loadMappings();
      }
    } catch {
      // ignore
    } finally {
      setLinking(false);
    }
  };

  const toggleSection = (sectionId: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  };

  useEffect(() => {
    if (open) {
      loadDetail();
      loadMappings();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1">
          <Eye className="h-3.5 w-3.5" />
          View
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[85vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {detail?.name || "Loading..."}
          </DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
          </div>
        ) : detail ? (
          <ScrollArea className="max-h-[65vh]">
            <div className="space-y-4 pr-4">
              {/* Meta info */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-muted-foreground">Status: </span>
                  <StatusBadge status={detail.status} />
                </div>
                <div>
                  <span className="text-muted-foreground">Version: </span>
                  <span className="font-mono">{detail.version || "N/A"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Organization: </span>
                  <span>{detail.source_organization || "N/A"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Uploaded: </span>
                  <span>
                    {detail.uploaded_at
                      ? new Date(detail.uploaded_at).toLocaleDateString()
                      : "N/A"}
                  </span>
                </div>
              </div>

              {detail.description && (
                <p className="text-sm text-muted-foreground">{detail.description}</p>
              )}

              <Separator />

              {/* Sections */}
              <div>
                <h3 className="font-semibold text-sm mb-2">
                  Sections ({detail.sections.length})
                </h3>
                <div className="space-y-1">
                  {detail.sections.map((section) => (
                    <div
                      key={section.id}
                      className="border rounded-lg"
                    >
                      <button
                        className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800"
                        onClick={() => toggleSection(section.id)}
                      >
                        {expandedSections.has(section.id) ? (
                          <ChevronDown className="h-4 w-4 shrink-0" />
                        ) : (
                          <ChevronRight className="h-4 w-4 shrink-0" />
                        )}
                        <span className="font-mono text-xs text-muted-foreground w-8">
                          {section.section_number}
                        </span>
                        <span className="font-medium truncate">{section.title}</span>
                        {section.has_embedding && (
                          <Badge
                            variant="outline"
                            className="ml-auto text-[10px] shrink-0 bg-blue-50 text-blue-700 border-blue-200"
                          >
                            embedded
                          </Badge>
                        )}
                      </button>
                      {expandedSections.has(section.id) && (
                        <div className="px-3 pb-3 text-sm text-muted-foreground border-t">
                          <p className="mt-2 whitespace-pre-wrap">{section.content_text}</p>
                          {section.keywords && section.keywords.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {section.keywords.slice(0, 10).map((kw) => (
                                <Badge key={kw} variant="secondary" className="text-[10px]">
                                  {kw}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <Separator />

              {/* Rule Mappings */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-sm">
                    Alert Rule Mappings ({mappings.length})
                  </h3>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleLinkRules}
                    disabled={linking}
                    className="gap-1"
                  >
                    {linking ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Link2 className="h-3.5 w-3.5" />
                    )}
                    Link Rules
                  </Button>
                </div>
                {mappings.length > 0 ? (
                  <div className="space-y-1">
                    {mappings.map((m) => (
                      <div
                        key={m.id}
                        className="flex items-center justify-between rounded border px-3 py-2 text-sm"
                      >
                        <span className="text-muted-foreground truncate">
                          {m.mapping_rationale}
                        </span>
                        <Badge
                          variant="outline"
                          className={`text-xs shrink-0 ml-2 ${
                            m.mapping_confidence >= 0.7
                              ? "bg-green-50 text-green-700 border-green-200"
                              : "bg-amber-50 text-amber-700 border-amber-200"
                          }`}
                        >
                          {(m.mapping_confidence * 100).toFixed(0)}%
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No rules linked yet. Click &ldquo;Link Rules&rdquo; to auto-match.
                  </p>
                )}
              </div>
            </div>
          </ScrollArea>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Search Panel
// =============================================================================

function PolicySearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (query.length < 3) return;
    setSearching(true);
    setSearched(true);
    try {
      const res = await fetch("/api/policies/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 10 }),
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
      }
    } catch {
      // ignore
    } finally {
      setSearching(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Search className="h-4 w-4" />
          Search Policies
        </CardTitle>
        <CardDescription>
          Semantic search across active policy sections
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2 mb-4">
          <Input
            placeholder="Search policy content..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <Button
            onClick={handleSearch}
            disabled={searching || query.length < 3}
            className="gap-1 shrink-0"
          >
            {searching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            Search
          </Button>
        </div>

        {searched && (
          <div className="space-y-2">
            {results.length > 0 ? (
              results.map((r) => (
                <div
                  key={r.section_id}
                  className="border rounded-lg p-3 text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium">{r.section_title}</div>
                      <div className="text-xs text-muted-foreground">
                        {r.policy_name}
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className={`text-xs shrink-0 ${
                        r.relevance_score >= 0.7
                          ? "bg-green-50 text-green-700 border-green-200"
                          : r.relevance_score >= 0.4
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : "bg-zinc-50 text-zinc-600 border-zinc-200"
                      }`}
                    >
                      {(r.relevance_score * 100).toFixed(0)}% match
                    </Badge>
                  </div>
                  <p className="mt-1 text-muted-foreground line-clamp-3">
                    {r.content_text}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                No matching policy sections found
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Main Page
// =============================================================================

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const loadPolicies = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const url =
        statusFilter !== "all"
          ? `/api/policies?status=${statusFilter}`
          : "/api/policies";
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setPolicies(data.policies || []);
      } else {
        setError("Failed to load policies");
      }
    } catch {
      setError("Network error loading policies");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadPolicies();
  }, [loadPolicies]);

  const handleStatusChange = async (policyId: string, newStatus: string) => {
    try {
      const res = await fetch(`/api/policies/${policyId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        loadPolicies();
      }
    } catch {
      // ignore
    }
  };

  const statusCounts = {
    all: policies.length,
    draft: policies.filter((p) => p.status === "draft").length,
    active: policies.filter((p) => p.status === "active").length,
    superseded: policies.filter((p) => p.status === "superseded").length,
    retired: policies.filter((p) => p.status === "retired").length,
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      {/* Header */}
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className="h-6 w-6 text-indigo-500" />
              <div>
                <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                  Policy Management
                </h1>
                <p className="text-sm text-muted-foreground">
                  Upload, manage, and search institutional clinical policies
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={loadPolicies}
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
              <UploadPolicyDialog onUploaded={loadPolicies} />
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {error ? (
          <Card className="mx-auto max-w-2xl">
            <CardContent className="py-8 text-center">
              <AlertCircle className="mx-auto h-12 w-12 text-red-400" />
              <p className="mt-2 text-zinc-500">{error}</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Policies</CardDescription>
                  <CardTitle className="text-3xl">{statusCounts.all}</CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Active</CardDescription>
                  <CardTitle className="text-3xl flex items-center gap-2">
                    {statusCounts.active}
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Draft</CardDescription>
                  <CardTitle className="text-3xl flex items-center gap-2">
                    {statusCounts.draft}
                    <Clock className="h-5 w-5 text-slate-400" />
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Retired/Superseded</CardDescription>
                  <CardTitle className="text-3xl">
                    {statusCounts.retired + statusCounts.superseded}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>

            {/* Search Panel */}
            <PolicySearchPanel />

            {/* Policies Table */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Policies</CardTitle>
                    <CardDescription>
                      Institutional policies with section parsing and rule linking
                    </CardDescription>
                  </div>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-40">
                      <SelectValue placeholder="Filter status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="superseded">Superseded</SelectItem>
                      <SelectItem value="retired">Retired</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                {isLoading && policies.length === 0 ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Policy</TableHead>
                        <TableHead>Organization</TableHead>
                        <TableHead>Version</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Uploaded</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {policies.map((policy) => (
                        <TableRow key={policy.id}>
                          <TableCell>
                            <div className="font-medium">{policy.name}</div>
                            {policy.description && (
                              <div className="text-xs text-muted-foreground truncate max-w-xs">
                                {policy.description}
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="text-sm">
                            {policy.source_organization || "—"}
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            {policy.version || "—"}
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={policy.status} />
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {policy.uploaded_at
                              ? new Date(policy.uploaded_at).toLocaleDateString()
                              : "—"}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <PolicyDetailDialog policyId={policy.id} />
                              {policy.status === "draft" && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="gap-1 text-green-700"
                                  onClick={() =>
                                    handleStatusChange(policy.id, "active")
                                  }
                                >
                                  <CheckCircle className="h-3.5 w-3.5" />
                                  Activate
                                </Button>
                              )}
                              {policy.status === "active" && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="gap-1 text-amber-700"
                                  onClick={() =>
                                    handleStatusChange(policy.id, "retired")
                                  }
                                >
                                  <Archive className="h-3.5 w-3.5" />
                                  Retire
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                      {policies.length === 0 && (
                        <TableRow>
                          <TableCell
                            colSpan={6}
                            className="text-center py-12 text-muted-foreground"
                          >
                            <Shield className="mx-auto h-12 w-12 text-zinc-300 mb-2" />
                            <p>No policies found</p>
                            <p className="text-xs mt-1">
                              Click &ldquo;Upload Policy&rdquo; to add your first institutional policy
                            </p>
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
