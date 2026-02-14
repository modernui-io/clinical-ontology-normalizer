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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  FileSpreadsheet,
  CheckSquare,
  Settings2,
  Upload,
  RefreshCw,
  Loader2,
  AlertCircle,
  LayoutList,
  Code2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types aligned with backend schemas
// ---------------------------------------------------------------------------

interface CRFManagementMetrics {
  total_crf_versions: number;
  versions_by_status: Record<string, number>;
  total_fields: number;
  fields_by_type: Record<string, number>;
  required_field_pct: number;
  total_edit_checks: number;
  edit_checks_by_severity: Record<string, number>;
  active_edit_check_pct: number;
  total_deployments: number;
  deployments_by_status: Record<string, number>;
  total_annotations: number;
  annotations_by_type: Record<string, number>;
  annotation_review_rate: number;
}

interface CRFVersion {
  id: string;
  trial_id: string;
  crf_name: string;
  version_number: string;
  crf_status: string;
  total_fields: number;
  total_pages: number;
  authored_by: string;
  reviewed_by: string | null;
  approved_by: string | null;
  effective_date: string | null;
  retirement_date: string | null;
  change_summary: string | null;
  notes: string | null;
  created_at: string;
}

interface CRFField {
  id: string;
  trial_id: string;
  crf_version_id: string;
  field_name: string;
  field_label: string;
  field_type: string;
  page_number: number;
  display_order: number;
  is_required: boolean;
  is_key_field: boolean;
  sdtm_domain: string | null;
  sdtm_variable: string | null;
  codelist_name: string | null;
  min_value: number | null;
  max_value: number | null;
  default_value: string | null;
  notes: string | null;
  created_at: string;
}

interface EditCheckRule {
  id: string;
  trial_id: string;
  crf_version_id: string;
  rule_name: string;
  rule_expression: string;
  edit_check_severity: string;
  target_field_id: string;
  error_message: string;
  is_active: boolean;
  fire_on_save: boolean;
  fire_on_submit: boolean;
  cross_form_check: boolean;
  reference_field_id: string | null;
  authored_by: string;
  notes: string | null;
  created_at: string;
}

interface CRFDeployment {
  id: string;
  trial_id: string;
  crf_version_id: string;
  deployment_status: string;
  target_environment: string;
  deployed_by: string;
  deployment_date: string | null;
  scheduled_date: string | null;
  sites_affected: number;
  subjects_affected: number;
  rollback_available: boolean;
  validation_passed: boolean;
  notes: string | null;
  created_at: string;
}

interface ListResponse<T> {
  items: T[];
  total: number;
}

// ---------------------------------------------------------------------------
// Badge color helpers
// ---------------------------------------------------------------------------

const versionStatusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  in_review: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  approved: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  deployed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300",
  retired: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  superseded: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
};

const fieldTypeColors: Record<string, string> = {
  text: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  numeric: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  date: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  dropdown: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-300",
  checkbox: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  radio: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-300",
};

const severityColors: Record<string, string> = {
  error: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  informational: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  hard_stop: "bg-red-200 text-red-900 dark:bg-red-950 dark:text-red-200",
  soft_check: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
};

const deploymentStatusColors: Record<string, string> = {
  pending: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  in_progress: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  rolled_back: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  scheduled: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
};

const environmentColors: Record<string, string> = {
  production: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  staging: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  development: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  uat: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CRFManagementPage() {
  const [metrics, setMetrics] = useState<CRFManagementMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState("versions");

  const [versions, setVersions] = useState<CRFVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState<string | null>(null);

  const [fields, setFields] = useState<CRFField[]>([]);
  const [fieldsLoading, setFieldsLoading] = useState(false);
  const [fieldsError, setFieldsError] = useState<string | null>(null);

  const [editChecks, setEditChecks] = useState<EditCheckRule[]>([]);
  const [editChecksLoading, setEditChecksLoading] = useState(false);
  const [editChecksError, setEditChecksError] = useState<string | null>(null);

  const [deployments, setDeployments] = useState<CRFDeployment[]>([]);
  const [deploymentsLoading, setDeploymentsLoading] = useState(false);
  const [deploymentsError, setDeploymentsError] = useState<string | null>(null);

  // ---- Fetchers ----

  const fetchMetrics = useCallback(async () => {
    setMetricsLoading(true);
    setMetricsError(null);
    try {
      const res = await fetch("/api/crf-management/metrics");
      if (!res.ok) throw new Error(`Failed to fetch metrics (${res.status})`);
      const data: CRFManagementMetrics = await res.json();
      setMetrics(data);
    } catch (err) {
      setMetricsError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setMetricsLoading(false);
    }
  }, []);

  const fetchVersions = useCallback(async () => {
    setVersionsLoading(true);
    setVersionsError(null);
    try {
      const res = await fetch("/api/crf-management/versions");
      if (!res.ok) throw new Error(`Failed to fetch versions (${res.status})`);
      const data: ListResponse<CRFVersion> = await res.json();
      setVersions(data.items);
    } catch (err) {
      setVersionsError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setVersionsLoading(false);
    }
  }, []);

  const fetchFields = useCallback(async () => {
    setFieldsLoading(true);
    setFieldsError(null);
    try {
      const res = await fetch("/api/crf-management/fields");
      if (!res.ok) throw new Error(`Failed to fetch fields (${res.status})`);
      const data: ListResponse<CRFField> = await res.json();
      setFields(data.items);
    } catch (err) {
      setFieldsError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setFieldsLoading(false);
    }
  }, []);

  const fetchEditChecks = useCallback(async () => {
    setEditChecksLoading(true);
    setEditChecksError(null);
    try {
      const res = await fetch("/api/crf-management/edit-check-rules");
      if (!res.ok) throw new Error(`Failed to fetch edit checks (${res.status})`);
      const data: ListResponse<EditCheckRule> = await res.json();
      setEditChecks(data.items);
    } catch (err) {
      setEditChecksError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setEditChecksLoading(false);
    }
  }, []);

  const fetchDeployments = useCallback(async () => {
    setDeploymentsLoading(true);
    setDeploymentsError(null);
    try {
      const res = await fetch("/api/crf-management/deployments");
      if (!res.ok) throw new Error(`Failed to fetch deployments (${res.status})`);
      const data: ListResponse<CRFDeployment> = await res.json();
      setDeployments(data.items);
    } catch (err) {
      setDeploymentsError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setDeploymentsLoading(false);
    }
  }, []);

  // ---- Initial loads ----

  useEffect(() => {
    fetchMetrics();
    fetchVersions();
  }, [fetchMetrics, fetchVersions]);

  // Fetch tab data when tab changes
  useEffect(() => {
    if (activeTab === "versions" && versions.length === 0 && !versionsLoading) {
      fetchVersions();
    } else if (activeTab === "fields" && fields.length === 0 && !fieldsLoading) {
      fetchFields();
    } else if (activeTab === "edit-checks" && editChecks.length === 0 && !editChecksLoading) {
      fetchEditChecks();
    } else if (activeTab === "deployments" && deployments.length === 0 && !deploymentsLoading) {
      fetchDeployments();
    }
  }, [
    activeTab,
    versions.length, versionsLoading, fetchVersions,
    fields.length, fieldsLoading, fetchFields,
    editChecks.length, editChecksLoading, fetchEditChecks,
    deployments.length, deploymentsLoading, fetchDeployments,
  ]);

  const handleRefresh = () => {
    fetchMetrics();
    if (activeTab === "versions") fetchVersions();
    else if (activeTab === "fields") fetchFields();
    else if (activeTab === "edit-checks") fetchEditChecks();
    else if (activeTab === "deployments") fetchDeployments();
  };

  // ---- Helpers ----

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString();
  }

  function truncate(str: string, max: number): string {
    return str.length > max ? str.slice(0, max) + "..." : str;
  }

  function renderLoading(label: string) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading {label}...</span>
      </div>
    );
  }

  function renderError(message: string) {
    return (
      <div className="flex items-center justify-center py-12 text-red-600">
        <AlertCircle className="h-5 w-5 mr-2" />
        <span>{message}</span>
      </div>
    );
  }

  function renderEmpty(label: string) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No {label} found
      </div>
    );
  }

  // ---- Render ----

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FileSpreadsheet className="h-6 w-6 text-blue-600" />
            CRF Management
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage case report form versions, fields, edit checks, and deployments
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">CRF Versions</CardTitle>
            <LayoutList className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {metricsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : metricsError ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{metrics?.total_crf_versions ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {metrics?.versions_by_status?.deployed ?? 0} deployed
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Fields Defined</CardTitle>
            <Settings2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {metricsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : metricsError ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{metrics?.total_fields ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {(metrics?.required_field_pct ?? 0).toFixed(1)}% required
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Edit Check Rules</CardTitle>
            <CheckSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {metricsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : metricsError ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{metrics?.total_edit_checks ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {(metrics?.active_edit_check_pct ?? 0).toFixed(1)}% active
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Deployments</CardTitle>
            <Upload className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {metricsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : metricsError ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{metrics?.total_deployments ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {metrics?.deployments_by_status?.completed ?? 0} completed
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="versions">
            <LayoutList className="mr-2 h-4 w-4" />
            Versions
          </TabsTrigger>
          <TabsTrigger value="fields">
            <Settings2 className="mr-2 h-4 w-4" />
            Fields
          </TabsTrigger>
          <TabsTrigger value="edit-checks">
            <Code2 className="mr-2 h-4 w-4" />
            Edit Checks
          </TabsTrigger>
          <TabsTrigger value="deployments">
            <Upload className="mr-2 h-4 w-4" />
            Deployments
          </TabsTrigger>
        </TabsList>

        {/* Versions Tab */}
        <TabsContent value="versions">
          <Card>
            <CardHeader>
              <CardTitle>CRF Versions</CardTitle>
              <CardDescription>
                All case report form versions across trials
              </CardDescription>
            </CardHeader>
            <CardContent>
              {versionsLoading ? renderLoading("versions") :
               versionsError ? renderError(versionsError) :
               versions.length === 0 ? renderEmpty("versions") : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Version ID</TableHead>
                        <TableHead>Form Name</TableHead>
                        <TableHead>Version</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Fields</TableHead>
                        <TableHead>Author</TableHead>
                        <TableHead>Created Date</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {versions.map((v) => (
                        <TableRow key={v.id}>
                          <TableCell className="font-mono text-sm">{v.id}</TableCell>
                          <TableCell className="font-medium">{v.crf_name}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{v.version_number}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge className={versionStatusColors[v.crf_status] || ""}>
                              {v.crf_status.replace(/_/g, " ")}
                            </Badge>
                          </TableCell>
                          <TableCell>{v.total_fields}</TableCell>
                          <TableCell>{v.authored_by}</TableCell>
                          <TableCell>{formatDate(v.created_at)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Fields Tab */}
        <TabsContent value="fields">
          <Card>
            <CardHeader>
              <CardTitle>CRF Fields</CardTitle>
              <CardDescription>
                Field definitions across all CRF versions
              </CardDescription>
            </CardHeader>
            <CardContent>
              {fieldsLoading ? renderLoading("fields") :
               fieldsError ? renderError(fieldsError) :
               fields.length === 0 ? renderEmpty("fields") : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Field ID</TableHead>
                        <TableHead>Field Name</TableHead>
                        <TableHead>Label</TableHead>
                        <TableHead>Field Type</TableHead>
                        <TableHead>Required</TableHead>
                        <TableHead>Key Field</TableHead>
                        <TableHead>CRF Version</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {fields.map((f) => (
                        <TableRow key={f.id}>
                          <TableCell className="font-mono text-sm">{f.id}</TableCell>
                          <TableCell className="font-medium">{f.field_name}</TableCell>
                          <TableCell>{f.field_label}</TableCell>
                          <TableCell>
                            <Badge className={fieldTypeColors[f.field_type] || ""}>
                              {f.field_type}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <span className={f.is_required ? "text-green-600 font-semibold" : "text-muted-foreground"}>
                              {f.is_required ? "Y" : "N"}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span className={f.is_key_field ? "text-blue-600 font-semibold" : "text-muted-foreground"}>
                              {f.is_key_field ? "Y" : "N"}
                            </span>
                          </TableCell>
                          <TableCell className="font-mono text-sm">{f.crf_version_id}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Edit Checks Tab */}
        <TabsContent value="edit-checks">
          <Card>
            <CardHeader>
              <CardTitle>Edit Check Rules</CardTitle>
              <CardDescription>
                Validation rules applied to CRF data entry
              </CardDescription>
            </CardHeader>
            <CardContent>
              {editChecksLoading ? renderLoading("edit checks") :
               editChecksError ? renderError(editChecksError) :
               editChecks.length === 0 ? renderEmpty("edit check rules") : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Rule ID</TableHead>
                        <TableHead>Rule Name</TableHead>
                        <TableHead>Severity</TableHead>
                        <TableHead>Expression</TableHead>
                        <TableHead>Active</TableHead>
                        <TableHead>Author</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {editChecks.map((r) => (
                        <TableRow key={r.id}>
                          <TableCell className="font-mono text-sm">{r.id}</TableCell>
                          <TableCell className="font-medium">{r.rule_name}</TableCell>
                          <TableCell>
                            <Badge className={severityColors[r.edit_check_severity] || ""}>
                              {r.edit_check_severity.replace(/_/g, " ")}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-sm max-w-[300px]">
                            {truncate(r.rule_expression, 60)}
                          </TableCell>
                          <TableCell>
                            <span className={r.is_active ? "text-green-600 font-semibold" : "text-red-500"}>
                              {r.is_active ? "Y" : "N"}
                            </span>
                          </TableCell>
                          <TableCell>{r.authored_by}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Deployments Tab */}
        <TabsContent value="deployments">
          <Card>
            <CardHeader>
              <CardTitle>CRF Deployments</CardTitle>
              <CardDescription>
                Deployment history and status tracking
              </CardDescription>
            </CardHeader>
            <CardContent>
              {deploymentsLoading ? renderLoading("deployments") :
               deploymentsError ? renderError(deploymentsError) :
               deployments.length === 0 ? renderEmpty("deployments") : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>Version</TableHead>
                        <TableHead>Environment</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Sites</TableHead>
                        <TableHead>Deployed By</TableHead>
                        <TableHead>Deployed Date</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {deployments.map((d) => (
                        <TableRow key={d.id}>
                          <TableCell className="font-mono text-sm">{d.id}</TableCell>
                          <TableCell className="font-mono text-sm">{d.crf_version_id}</TableCell>
                          <TableCell>
                            <Badge className={environmentColors[d.target_environment.toLowerCase()] || "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300"}>
                              {d.target_environment}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge className={deploymentStatusColors[d.deployment_status] || ""}>
                              {d.deployment_status.replace(/_/g, " ")}
                            </Badge>
                          </TableCell>
                          <TableCell>{d.sites_affected}</TableCell>
                          <TableCell>{d.deployed_by}</TableCell>
                          <TableCell>{formatDate(d.deployment_date)}</TableCell>
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
