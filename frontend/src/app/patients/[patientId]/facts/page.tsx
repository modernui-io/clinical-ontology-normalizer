"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getPatientFacts, ClinicalFact } from "@/lib/api";

const ASSERTION_COLORS: Record<string, string> = {
  present: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-200",
  absent: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-200",
  possible: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200",
};

const DOMAIN_COLORS: Record<string, string> = {
  condition: "bg-red-100 text-red-800",
  drug: "bg-blue-100 text-blue-800",
  measurement: "bg-green-100 text-green-800",
  procedure: "bg-orange-100 text-orange-800",
  observation: "bg-gray-100 text-gray-800",
};

const DOMAIN_OPTIONS = ["condition", "drug", "measurement", "procedure", "observation"];
const ASSERTION_OPTIONS = ["present", "absent", "possible"];

export default function PatientFactsPage() {
  const params = useParams();
  const patientId = params.patientId as string;
  const [facts, setFacts] = useState<ClinicalFact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [domainFilter, setDomainFilter] = useState<string | undefined>();
  const [assertionFilter, setAssertionFilter] = useState<string | undefined>();
  const [viewMode, setViewMode] = useState<"table" | "grouped">("grouped");

  const fetchFacts = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await getPatientFacts(patientId, {
        domain: domainFilter,
        assertion: assertionFilter,
      });
      setFacts(result);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch facts:", err);
      setError("No clinical facts found for this patient.");
      setFacts([]);
    } finally {
      setIsLoading(false);
    }
  }, [patientId, domainFilter, assertionFilter]);

  useEffect(() => {
    if (!patientId) return;
    fetchFacts();
  }, [patientId, fetchFacts]);

  // Group facts by domain for summary
  const factsByDomain = facts.reduce(
    (acc, fact) => {
      if (!acc[fact.domain]) acc[fact.domain] = [];
      acc[fact.domain].push(fact);
      return acc;
    },
    {} as Record<string, ClinicalFact[]>
  );

  // Count negated facts
  const negatedCount = facts.filter((f) => f.assertion === "absent").length;
  const uncertainCount = facts.filter((f) => f.assertion === "possible").length;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/patients" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                &larr; Patients
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Patient {patientId} - Clinical Facts
              </h1>
            </div>
            <Link href={`/patients/${patientId}/graph`}>
              <Button variant="outline">View Knowledge Graph</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
          </div>
        ) : error && facts.length === 0 ? (
          <Card className="mx-auto max-w-2xl">
            <CardContent className="py-8 text-center">
              <p className="text-zinc-500">{error}</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid gap-4 md:grid-cols-5">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Total Facts</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{facts.length}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Present</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-600">
                    {facts.length - negatedCount - uncertainCount}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Negated</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-red-600">{negatedCount}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Uncertain</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-yellow-600">{uncertainCount}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Domains</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{Object.keys(factsByDomain).length}</div>
                </CardContent>
              </Card>
            </div>

            {/* Filters */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Filters</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-4 flex-wrap">
                  <div>
                    <label className="text-sm font-medium text-zinc-500 mb-1 block">Domain</label>
                    <select
                      className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={domainFilter || ""}
                      onChange={(e) => setDomainFilter(e.target.value || undefined)}
                    >
                      <option value="">All domains</option>
                      {DOMAIN_OPTIONS.map((domain) => (
                        <option key={domain} value={domain}>
                          {domain.charAt(0).toUpperCase() + domain.slice(1)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-zinc-500 mb-1 block">Assertion</label>
                    <select
                      className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={assertionFilter || ""}
                      onChange={(e) => setAssertionFilter(e.target.value || undefined)}
                    >
                      <option value="">All assertions</option>
                      {ASSERTION_OPTIONS.map((assertion) => (
                        <option key={assertion} value={assertion}>
                          {assertion.charAt(0).toUpperCase() + assertion.slice(1)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end gap-2">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setDomainFilter(undefined);
                        setAssertionFilter(undefined);
                      }}
                    >
                      Clear Filters
                    </Button>
                    <div className="border-l pl-2 flex gap-1">
                      <Button
                        variant={viewMode === "grouped" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setViewMode("grouped")}
                      >
                        Grouped
                      </Button>
                      <Button
                        variant={viewMode === "table" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setViewMode("table")}
                      >
                        Table
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Grouped View */}
            {viewMode === "grouped" && (
              <div className="space-y-4">
                {Object.entries(factsByDomain)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([domain, domainFacts]) => (
                    <Card key={domain}>
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-lg flex items-center gap-2">
                            <Badge className={DOMAIN_COLORS[domain] || "bg-gray-100"}>
                              {domain.charAt(0).toUpperCase() + domain.slice(1)}
                            </Badge>
                            <span className="text-sm font-normal text-zinc-500">
                              {domainFacts.length} fact{domainFacts.length !== 1 ? "s" : ""}
                            </span>
                          </CardTitle>
                          <div className="flex gap-1">
                            {domainFacts.filter((f) => f.assertion === "present").length > 0 && (
                              <Badge className={ASSERTION_COLORS["present"]}>
                                {domainFacts.filter((f) => f.assertion === "present").length} present
                              </Badge>
                            )}
                            {domainFacts.filter((f) => f.assertion === "absent").length > 0 && (
                              <Badge className={ASSERTION_COLORS["absent"]}>
                                {domainFacts.filter((f) => f.assertion === "absent").length} absent
                              </Badge>
                            )}
                            {domainFacts.filter((f) => f.assertion === "possible").length > 0 && (
                              <Badge className={ASSERTION_COLORS["possible"]}>
                                {domainFacts.filter((f) => f.assertion === "possible").length} possible
                              </Badge>
                            )}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {domainFacts.map((fact) => (
                            <div
                              key={fact.id}
                              className="flex items-center justify-between p-2 rounded border"
                            >
                              <div className="flex items-center gap-3">
                                <Badge className={ASSERTION_COLORS[fact.assertion] || "bg-gray-100"} variant="outline">
                                  {fact.assertion}
                                </Badge>
                                <span className="font-medium text-sm">{fact.concept_name}</span>
                                {fact.value && (
                                  <span className="text-sm text-zinc-500">
                                    {fact.value}{fact.unit ? ` ${fact.unit}` : ""}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2 text-xs text-zinc-500">
                                <span className="capitalize">{fact.temporality}</span>
                                <span className={fact.confidence >= 0.8 ? "text-green-600" : fact.confidence >= 0.5 ? "text-yellow-600" : "text-red-600"}>
                                  {(fact.confidence * 100).toFixed(0)}%
                                </span>
                                <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">
                                  {fact.omop_concept_id}
                                </code>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                {facts.length === 0 && (
                  <div className="text-center py-8 text-zinc-500">
                    No facts match the current filters.
                  </div>
                )}
              </div>
            )}

            {/* Facts Table */}
            {viewMode === "table" && (
            <Card>
              <CardHeader>
                <CardTitle>Clinical Facts</CardTitle>
                <CardDescription>
                  Normalized clinical findings extracted from documents
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Domain</TableHead>
                      <TableHead>Concept</TableHead>
                      <TableHead>OMOP ID</TableHead>
                      <TableHead>Assertion</TableHead>
                      <TableHead>Temporality</TableHead>
                      <TableHead>Experiencer</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {facts.map((fact) => (
                      <TableRow key={fact.id}>
                        <TableCell>
                          <Badge className={DOMAIN_COLORS[fact.domain] || "bg-gray-100"}>
                            {fact.domain}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium max-w-xs truncate">
                          {fact.concept_name}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {fact.omop_concept_id}
                        </TableCell>
                        <TableCell>
                          <Badge className={ASSERTION_COLORS[fact.assertion] || "bg-gray-100"}>
                            {fact.assertion}
                          </Badge>
                        </TableCell>
                        <TableCell className="capitalize">{fact.temporality}</TableCell>
                        <TableCell className="capitalize">{fact.experiencer}</TableCell>
                        <TableCell>
                          <span className={fact.confidence >= 0.8 ? "text-green-600" : fact.confidence >= 0.5 ? "text-yellow-600" : "text-red-600"}>
                            {(fact.confidence * 100).toFixed(0)}%
                          </span>
                        </TableCell>
                        <TableCell>
                          {fact.value ? `${fact.value}${fact.unit ? ` ${fact.unit}` : ""}` : "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {facts.length === 0 && (
                  <div className="text-center py-8 text-zinc-500">
                    No facts match the current filters.
                  </div>
                )}
              </CardContent>
            </Card>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
