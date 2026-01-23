"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  BookOpen,
  Search,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

interface ValueSetSummary {
  id: string;
  name: string;
  title: string | null;
  description: string | null;
  url: string | null;
  version: string;
  status: string;
  value_set_type: string;
  code_count: number;
}

interface ValueSetCode {
  system: string;
  code: string;
  display: string;
  inactive: boolean;
}

interface ExpansionResult {
  value_set_id: string;
  total: number;
  offset: number;
  codes: ValueSetCode[];
}

interface ValidationResult {
  valid: boolean;
  message: string | null;
  display: string | null;
}

const statusColors: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  draft: "bg-yellow-100 text-yellow-800",
  retired: "bg-gray-100 text-gray-800",
};

export default function ValueSetBrowserPage() {
  const [valueSets, setValueSets] = useState<ValueSetSummary[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expansionCodes, setExpansionCodes] = useState<ValueSetCode[]>([]);
  const [expansionTotal, setExpansionTotal] = useState(0);
  const [isExpanding, setIsExpanding] = useState(false);

  // Validation state
  const [validateVsId, setValidateVsId] = useState("");
  const [validateSystem, setValidateSystem] = useState("");
  const [validateCode, setValidateCode] = useState("");
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const fetchValueSets = useCallback(async (query?: string) => {
    setIsLoading(true);
    setHasSearched(true);
    try {
      const params = new URLSearchParams();
      if (query && query.trim().length >= 2) {
        params.set("search", query.trim());
      }
      params.set("limit", "50");
      const res = await fetch(`${API_BASE}/api/v1/valuesets?${params}`);
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setValueSets(data.value_sets || []);
    } catch {
      setValueSets([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const expandValueSet = useCallback(async (vsId: string) => {
    if (expandedId === vsId) {
      setExpandedId(null);
      return;
    }
    setIsExpanding(true);
    setExpandedId(vsId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/valuesets/${vsId}/$expand?count=50`);
      if (!res.ok) throw new Error("Failed to expand");
      const data: ExpansionResult = await res.json();
      setExpansionCodes(data.codes || []);
      setExpansionTotal(data.total || 0);
    } catch {
      setExpansionCodes([]);
      setExpansionTotal(0);
    } finally {
      setIsExpanding(false);
    }
  }, [expandedId]);

  const validateCodeInSet = useCallback(async () => {
    if (!validateVsId || !validateSystem || !validateCode) return;
    setIsValidating(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/valuesets/${validateVsId}/$validate-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ system: validateSystem, code: validateCode }),
      });
      if (!res.ok) throw new Error("Failed to validate");
      const data: ValidationResult = await res.json();
      setValidationResult(data);
    } catch {
      setValidationResult({ valid: false, message: "Validation request failed", display: null });
    } finally {
      setIsValidating(false);
    }
  }, [validateVsId, validateSystem, validateCode]);

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Value Set Browser</h1>
          <p className="text-muted-foreground">
            Browse, expand, and validate clinical value sets
          </p>
        </div>
      </div>

      {/* Search */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <BookOpen className="h-5 w-5" /> Search Value Sets
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, title, or description..."
              onKeyDown={(e) => e.key === "Enter" && fetchValueSets(searchQuery)}
            />
            <Button onClick={() => fetchValueSets(searchQuery)} disabled={isLoading}>
              <Search className="h-4 w-4 mr-1" />
              Search
            </Button>
            <Button variant="outline" onClick={() => fetchValueSets()}>
              All
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {hasSearched && (
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">
              Value Sets ({valueSets.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900" />
              </div>
            ) : valueSets.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No value sets found.
              </div>
            ) : (
              <div className="space-y-2">
                {valueSets.map((vs) => (
                  <div key={vs.id}>
                    <div
                      className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 cursor-pointer"
                      onClick={() => expandValueSet(vs.id)}
                    >
                      <div className="flex items-center gap-3">
                        {expandedId === vs.id ? (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}
                        <div>
                          <div className="font-medium text-sm">{vs.title || vs.name}</div>
                          {vs.description && (
                            <div className="text-xs text-muted-foreground truncate max-w-lg">
                              {vs.description}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={statusColors[vs.status] || "bg-gray-100"}>
                          {vs.status}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {vs.value_set_type}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {vs.code_count} codes
                        </span>
                        <span className="text-xs text-muted-foreground font-mono">
                          v{vs.version}
                        </span>
                      </div>
                    </div>

                    {/* Expanded codes */}
                    {expandedId === vs.id && (
                      <div className="ml-8 mt-1 mb-3 p-3 rounded border bg-muted/20">
                        {isExpanding ? (
                          <div className="flex justify-center py-4">
                            <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900" />
                          </div>
                        ) : expansionCodes.length === 0 ? (
                          <div className="text-sm text-muted-foreground py-2">
                            No codes in this value set.
                          </div>
                        ) : (
                          <>
                            <div className="text-xs text-muted-foreground mb-2">
                              Showing {expansionCodes.length} of {expansionTotal} codes
                            </div>
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead className="text-xs">System</TableHead>
                                  <TableHead className="text-xs">Code</TableHead>
                                  <TableHead className="text-xs">Display</TableHead>
                                  <TableHead className="text-xs">Status</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {expansionCodes.map((code, idx) => (
                                  <TableRow key={`${code.system}-${code.code}-${idx}`}>
                                    <TableCell className="text-xs font-mono truncate max-w-[200px]">
                                      {code.system}
                                    </TableCell>
                                    <TableCell className="text-xs font-mono font-medium">
                                      {code.code}
                                    </TableCell>
                                    <TableCell className="text-xs">{code.display}</TableCell>
                                    <TableCell>
                                      {code.inactive ? (
                                        <Badge variant="outline" className="text-xs text-red-600">inactive</Badge>
                                      ) : (
                                        <Badge variant="outline" className="text-xs text-green-600">active</Badge>
                                      )}
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Code Validation */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Validate Code</CardTitle>
          <CardDescription>
            Check if a code is a member of a value set
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Value Set ID</label>
              <Input
                value={validateVsId}
                onChange={(e) => setValidateVsId(e.target.value)}
                placeholder="vs-diabetes-diagnoses"
                className="text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Code System</label>
              <Input
                value={validateSystem}
                onChange={(e) => setValidateSystem(e.target.value)}
                placeholder="http://hl7.org/fhir/sid/icd-10-cm"
                className="text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Code</label>
              <Input
                value={validateCode}
                onChange={(e) => setValidateCode(e.target.value)}
                placeholder="E11.9"
                className="text-sm"
              />
            </div>
            <div className="flex items-end">
              <Button onClick={validateCodeInSet} disabled={isValidating || !validateVsId || !validateCode}>
                Validate
              </Button>
            </div>
          </div>

          {validationResult && (
            <div className={`mt-3 p-3 rounded-lg flex items-center gap-2 ${
              validationResult.valid ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
            }`}>
              {validationResult.valid ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              <div>
                <span className="font-medium text-sm">
                  {validationResult.valid ? "Valid" : "Invalid"}
                </span>
                {validationResult.message && (
                  <span className="text-sm ml-2">{validationResult.message}</span>
                )}
                {validationResult.display && (
                  <span className="text-sm ml-2">— {validationResult.display}</span>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
