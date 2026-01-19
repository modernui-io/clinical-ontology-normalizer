"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
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
  Search,
  ArrowLeft,
  CheckCircle,
  XCircle,
  RefreshCw,
  Copy,
  Check,
  BookOpen,
  Tag,
  FileCode,
  Info,
  ExternalLink,
  Lightbulb,
} from "lucide-react";

// Types
interface Term {
  code: string;
  submission_value: string;
  preferred_term: string;
  definition: string;
  synonyms: string[];
  ordinal: number;
  nci_code?: string;
}

interface CodelistDetail {
  c_code: string;
  name: string;
  submission_value: string;
  definition: string;
  codelist_type: string;
  domain: string;
  domain_description: string;
  term_count: number;
  version: string;
  nci_preferred_term: string;
  related_codelists: string[];
  terms: Term[];
}

interface ValidationResult {
  is_valid: boolean;
  codelist_code: string;
  codelist_name: string;
  submitted_value: string;
  matched_submission_value: string | null;
  matched_preferred_term: string | null;
  message: string;
  is_extensible: boolean;
  suggestions: Array<{
    code: string;
    submission_value: string;
    preferred_term: string;
  }>;
}

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CodelistDetailPage() {
  const params = useParams();
  const router = useRouter();
  const cCode = params.cCode as string;

  // State
  const [codelist, setCodelist] = useState<CodelistDetail | null>(null);
  const [filteredTerms, setFilteredTerms] = useState<Term[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Validation state
  const [validateValue, setValidateValue] = useState("");
  const [validationResult, setValidationResult] =
    useState<ValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  // Copy state
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  // Fetch codelist data
  useEffect(() => {
    const fetchCodelist = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const res = await fetch(
          `${API_BASE}/api/v1/cdisc/codelists/${cCode}?include_terms=true`
        );

        if (!res.ok) {
          if (res.status === 404) {
            throw new Error(`Codelist ${cCode} not found`);
          }
          throw new Error("Failed to fetch codelist");
        }

        const data = await res.json();
        setCodelist(data);
        setFilteredTerms(data.terms);
      } catch (err) {
        console.error("Error fetching codelist:", err);
        setError(
          err instanceof Error ? err.message : "Failed to load codelist"
        );
      } finally {
        setIsLoading(false);
      }
    };

    if (cCode) {
      fetchCodelist();
    }
  }, [cCode]);

  // Filter terms when search changes
  useEffect(() => {
    if (!codelist) return;

    if (!searchQuery.trim()) {
      setFilteredTerms(codelist.terms);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = codelist.terms.filter(
      (term) =>
        term.submission_value.toLowerCase().includes(query) ||
        term.preferred_term.toLowerCase().includes(query) ||
        term.definition.toLowerCase().includes(query) ||
        term.synonyms.some((s) => s.toLowerCase().includes(query))
    );
    setFilteredTerms(filtered);
  }, [searchQuery, codelist]);

  // Validate a value
  const handleValidate = useCallback(async () => {
    if (!validateValue.trim() || !codelist) return;

    setIsValidating(true);
    setValidationResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/cdisc/validate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          codelist: codelist.c_code,
          value: validateValue,
          strict: true,
        }),
      });

      if (!res.ok) {
        throw new Error("Validation failed");
      }

      const data = await res.json();
      setValidationResult(data);
    } catch (err) {
      console.error("Validation error:", err);
    } finally {
      setIsValidating(false);
    }
  }, [validateValue, codelist]);

  // Copy to clipboard
  const copyToClipboard = async (text: string, code: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedCode(code);
      setTimeout(() => setCopiedCode(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  // Handle validation on Enter
  const handleValidateKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleValidate();
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !codelist) {
    return (
      <div className="p-6">
        <Card className="border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
          <CardHeader>
            <CardTitle className="text-red-700 dark:text-red-400">
              Error Loading Codelist
            </CardTitle>
            <CardDescription className="text-red-600 dark:text-red-300">
              {error || "Codelist not found"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push("/cdisc")} variant="outline">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Browser
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isExtensible = codelist.codelist_type === "extensible";

  return (
    <div className="p-6 space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link
          href="/cdisc"
          className="hover:text-foreground transition-colors flex items-center gap-1"
        >
          <BookOpen className="h-4 w-4" />
          CDISC Browser
        </Link>
        <span>/</span>
        <span className="text-foreground">{codelist.submission_value}</span>
      </div>

      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">
              {codelist.submission_value}
            </h1>
            <Badge variant="outline" className="font-mono">
              {codelist.c_code}
            </Badge>
            <Badge
              className={
                isExtensible
                  ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                  : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
              }
            >
              {isExtensible ? (
                <CheckCircle className="mr-1 h-3 w-3" />
              ) : (
                <XCircle className="mr-1 h-3 w-3" />
              )}
              {codelist.codelist_type}
            </Badge>
          </div>
          <h2 className="text-lg text-muted-foreground">{codelist.name}</h2>
          <p className="text-sm text-muted-foreground max-w-2xl">
            {codelist.definition}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => router.push("/cdisc")}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Browser
        </Button>
      </div>

      {/* Codelist Info Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Domain</CardTitle>
            <FileCode className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{codelist.domain}</div>
            <p className="text-xs text-muted-foreground">
              {codelist.domain_description}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Terms</CardTitle>
            <Tag className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{codelist.term_count}</div>
            <p className="text-xs text-muted-foreground">
              Controlled terminology values
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Version</CardTitle>
            <Info className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">
              {codelist.version}
            </div>
            <p className="text-xs text-muted-foreground">CDISC CT Release</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Extensibility
            </CardTitle>
            {isExtensible ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
          </CardHeader>
          <CardContent>
            <div
              className={`text-lg font-bold ${
                isExtensible
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {isExtensible ? "Extensible" : "Non-Extensible"}
            </div>
            <p className="text-xs text-muted-foreground">
              {isExtensible
                ? "Sponsor-defined terms allowed"
                : "Must use defined terms only"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Validation Tool */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5" />
            Term Validation
          </CardTitle>
          <CardDescription>
            Validate a value against this codelist to check if it is a valid
            submission value
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="flex-1">
              <Input
                placeholder="Enter a value to validate (e.g., M, Male, MALE)..."
                value={validateValue}
                onChange={(e) => setValidateValue(e.target.value)}
                onKeyDown={handleValidateKeyDown}
              />
            </div>
            <Button onClick={handleValidate} disabled={isValidating}>
              {isValidating ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle className="mr-2 h-4 w-4" />
              )}
              Validate
            </Button>
          </div>

          {validationResult && (
            <div
              className={`mt-4 p-4 rounded-lg border ${
                validationResult.is_valid
                  ? "bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-900"
                  : "bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-900"
              }`}
            >
              <div className="flex items-start gap-3">
                {validationResult.is_valid ? (
                  <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5" />
                )}
                <div className="space-y-2">
                  <p
                    className={`font-medium ${
                      validationResult.is_valid
                        ? "text-green-700 dark:text-green-300"
                        : "text-red-700 dark:text-red-300"
                    }`}
                  >
                    {validationResult.is_valid ? "Valid" : "Invalid"}:{" "}
                    &ldquo;{validationResult.submitted_value}&rdquo;
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {validationResult.message}
                  </p>
                  {validationResult.matched_submission_value && (
                    <p className="text-sm">
                      <span className="font-medium">Submission Value:</span>{" "}
                      <code className="bg-muted px-1.5 py-0.5 rounded">
                        {validationResult.matched_submission_value}
                      </code>
                    </p>
                  )}
                  {validationResult.matched_preferred_term && (
                    <p className="text-sm">
                      <span className="font-medium">Preferred Term:</span>{" "}
                      {validationResult.matched_preferred_term}
                    </p>
                  )}
                  {validationResult.suggestions.length > 0 && (
                    <div className="mt-2">
                      <p className="text-sm font-medium flex items-center gap-1">
                        <Lightbulb className="h-4 w-4" />
                        Did you mean:
                      </p>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {validationResult.suggestions.map((s) => (
                          <Badge
                            key={s.code}
                            variant="secondary"
                            className="cursor-pointer hover:bg-muted"
                            onClick={() => setValidateValue(s.submission_value)}
                          >
                            {s.submission_value} ({s.preferred_term})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Terms Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Terms ({filteredTerms.length})</CardTitle>
              <CardDescription>
                Controlled terminology values for {codelist.submission_value}
              </CardDescription>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Filter terms..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 w-full sm:w-[300px]"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[60px]">#</TableHead>
                  <TableHead>Submission Value</TableHead>
                  <TableHead>Preferred Term</TableHead>
                  <TableHead className="hidden md:table-cell">Definition</TableHead>
                  <TableHead className="hidden lg:table-cell">Synonyms</TableHead>
                  <TableHead className="w-[80px]">NCI Code</TableHead>
                  <TableHead className="w-[60px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTerms.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8">
                      <p className="text-muted-foreground">
                        {searchQuery
                          ? `No terms matching "${searchQuery}"`
                          : "No terms found"}
                      </p>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredTerms.map((term) => (
                    <TableRow key={term.code}>
                      <TableCell className="text-muted-foreground font-mono text-sm">
                        {term.ordinal}
                      </TableCell>
                      <TableCell>
                        <code className="bg-muted px-2 py-1 rounded font-medium">
                          {term.submission_value}
                        </code>
                      </TableCell>
                      <TableCell className="font-medium">
                        {term.preferred_term}
                      </TableCell>
                      <TableCell className="hidden md:table-cell max-w-[300px]">
                        <span className="text-sm text-muted-foreground line-clamp-2">
                          {term.definition || "-"}
                        </span>
                      </TableCell>
                      <TableCell className="hidden lg:table-cell max-w-[200px]">
                        <div className="flex flex-wrap gap-1">
                          {term.synonyms.slice(0, 3).map((syn, idx) => (
                            <Badge
                              key={idx}
                              variant="outline"
                              className="text-xs"
                            >
                              {syn}
                            </Badge>
                          ))}
                          {term.synonyms.length > 3 && (
                            <Badge variant="secondary" className="text-xs">
                              +{term.synonyms.length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {term.code}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            copyToClipboard(term.submission_value, term.code)
                          }
                        >
                          {copiedCode === term.code ? (
                            <Check className="h-4 w-4 text-green-500" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Usage Examples */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCode className="h-5 w-5" />
            Usage Examples
          </CardTitle>
          <CardDescription>
            How to use the {codelist.submission_value} codelist in SDTM
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* SDTM Usage */}
            <div>
              <h4 className="text-sm font-medium mb-2">SDTM Variable Usage</h4>
              <div className="bg-muted p-4 rounded-lg">
                <code className="text-sm">
                  <span className="text-blue-600 dark:text-blue-400">
                    {codelist.domain}
                  </span>
                  .
                  <span className="text-green-600 dark:text-green-400">
                    {codelist.submission_value}
                  </span>{" "}
                  = &quot;
                  {codelist.terms[0]?.submission_value || "VALUE"}
                  &quot;
                </code>
              </div>
            </div>

            {/* Example Values */}
            <div>
              <h4 className="text-sm font-medium mb-2">Example Values</h4>
              <div className="flex flex-wrap gap-2">
                {codelist.terms.slice(0, 5).map((term) => (
                  <div
                    key={term.code}
                    className="bg-muted p-2 rounded-lg text-sm"
                  >
                    <code className="font-medium">{term.submission_value}</code>
                    <span className="text-muted-foreground ml-2">
                      ({term.preferred_term})
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* NCI EVS Link */}
            <div>
              <h4 className="text-sm font-medium mb-2">External Resources</h4>
              <a
                href={`https://ncithesaurus.nci.nih.gov/ncitbrowser/ConceptReport.jsp?dictionary=NCI_Thesaurus&code=${codelist.c_code}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline dark:text-blue-400"
              >
                View {codelist.c_code} in NCI Thesaurus
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Related Codelists */}
      {codelist.related_codelists && codelist.related_codelists.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Related Codelists</CardTitle>
            <CardDescription>
              Other codelists related to {codelist.submission_value}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {codelist.related_codelists.map((relatedCode) => (
                <Link key={relatedCode} href={`/cdisc/codelists/${relatedCode}`}>
                  <Badge
                    variant="outline"
                    className="cursor-pointer hover:bg-muted"
                  >
                    {relatedCode}
                  </Badge>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
