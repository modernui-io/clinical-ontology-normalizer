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
  ClipboardList,
  FileSpreadsheet,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckSquare,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types aligned with backend schemas
// ---------------------------------------------------------------------------

interface EDCFormField {
  id: string;
  field_name: string;
  label: string;
  field_type: string;
  required: boolean;
  validation_rules: string[];
  options: string[] | null;
  help_text: string | null;
}

interface EDCFormTemplate {
  id: string;
  trial_id: string;
  form_name: string;
  version: string;
  visit_applicability: string[];
  fields: EDCFormField[];
  status: string;
  created_at: string;
  updated_at: string;
  created_by: string;
}

interface ListResponse {
  items: EDCFormTemplate[];
  total: number;
}

// ---------------------------------------------------------------------------
// Badge color helpers
// ---------------------------------------------------------------------------

const statusColors: Record<string, string> = {
  published: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  retired: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
};

const fieldTypeColors: Record<string, string> = {
  text: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  number: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  date: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  select: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-300",
  checkbox: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  radio: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-300",
  textarea: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EDCPage() {
  const [templates, setTemplates] = useState<EDCFormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // ---- Fetcher ----

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/edc/templates");
      if (!res.ok) throw new Error(`Failed to fetch templates (${res.status})`);
      const data: ListResponse = await res.json();
      setTemplates(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  // ---- Initial load ----

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleRefresh = () => {
    fetchTemplates();
  };

  // ---- Computed metrics ----

  const totalTemplates = templates.length;
  const publishedCount = templates.filter((t) => t.status === "published").length;
  const draftCount = templates.filter((t) => t.status === "draft").length;
  const totalFields = templates.reduce((sum, t) => sum + t.fields.length, 0);

  // ---- Helpers ----

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString();
  }

  function toggleExpandRow(id: string) {
    setExpandedRow(expandedRow === id ? null : id);
  }

  // ---- Render ----

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ClipboardList className="h-6 w-6 text-blue-600" />
            EDC Forms
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Electronic Data Capture form templates and field definitions
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Templates</CardTitle>
            <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : error ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{totalTemplates}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Form templates
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Published</CardTitle>
            <CheckSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : error ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{publishedCount}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Active forms
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Draft</CardTitle>
            <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : error ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{draftCount}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  In development
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Fields</CardTitle>
            <ClipboardList className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : error ? (
              <span className="text-sm text-red-500">Error</span>
            ) : (
              <>
                <div className="text-2xl font-bold">{totalFields}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Across all forms
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Templates Table */}
      <Card>
        <CardHeader>
          <CardTitle>Form Templates</CardTitle>
          <CardDescription>
            All EDC form templates across trials
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">Loading templates...</span>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-12 text-red-600">
              <AlertCircle className="h-5 w-5 mr-2" />
              <span>{error}</span>
            </div>
          ) : templates.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              No form templates found
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Form Name</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Visit Applicability</TableHead>
                    <TableHead>Fields Count</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created By</TableHead>
                    <TableHead>Last Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {templates.map((template) => (
                    <>
                      <TableRow key={template.id} className="cursor-pointer hover:bg-muted/50" onClick={() => toggleExpandRow(template.id)}>
                        <TableCell>
                          <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                            {expandedRow === template.id ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </Button>
                        </TableCell>
                        <TableCell className="font-medium">{template.form_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{template.version}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {template.visit_applicability.slice(0, 2).map((visit, idx) => (
                              <Badge key={idx} variant="secondary" className="text-xs">
                                {visit}
                              </Badge>
                            ))}
                            {template.visit_applicability.length > 2 && (
                              <Badge variant="secondary" className="text-xs">
                                +{template.visit_applicability.length - 2}
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="font-semibold">{template.fields.length}</span>
                        </TableCell>
                        <TableCell>
                          <Badge className={statusColors[template.status] || ""}>
                            {template.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{template.created_by}</TableCell>
                        <TableCell>{formatDate(template.updated_at)}</TableCell>
                      </TableRow>
                      {expandedRow === template.id && (
                        <TableRow>
                          <TableCell colSpan={8} className="bg-muted/30 p-0">
                            <div className="p-4 space-y-2">
                              <h4 className="font-semibold text-sm mb-3 flex items-center gap-2">
                                <CheckSquare className="h-4 w-4" />
                                Fields ({template.fields.length})
                              </h4>
                              <div className="space-y-2 max-h-96 overflow-y-auto">
                                {template.fields.map((field) => (
                                  <div key={field.id} className="flex items-center gap-3 p-3 bg-background rounded-md border">
                                    <div className="flex-1">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="font-medium text-sm">{field.label}</span>
                                        {field.required && (
                                          <Badge variant="destructive" className="text-xs">
                                            Required
                                          </Badge>
                                        )}
                                        <Badge className={`${fieldTypeColors[field.field_type] || ""} text-xs`}>
                                          {field.field_type}
                                        </Badge>
                                      </div>
                                      <div className="text-xs text-muted-foreground">
                                        Field name: <span className="font-mono">{field.field_name}</span>
                                      </div>
                                      {field.help_text && (
                                        <div className="text-xs text-muted-foreground mt-1">
                                          {field.help_text}
                                        </div>
                                      )}
                                      {field.validation_rules.length > 0 && (
                                        <div className="text-xs text-muted-foreground mt-1">
                                          Validations: {field.validation_rules.join(", ")}
                                        </div>
                                      )}
                                      {field.options && field.options.length > 0 && (
                                        <div className="text-xs text-muted-foreground mt-1">
                                          Options: {field.options.join(", ")}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
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
