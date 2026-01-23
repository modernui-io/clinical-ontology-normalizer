"use client";

import { useState, useCallback } from "react";
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
  ArrowLeft,
  Search,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  FileText,
} from "lucide-react";

interface ICD10Code {
  code: string;
  description: string;
  category: string;
  is_billable: boolean;
  parent_code: string | null;
  synonyms: string[];
}

interface SearchResult {
  query: string;
  total_results: number;
  offset: number;
  limit: number;
  has_more: boolean;
  codes: ICD10Code[];
}

export default function ICD10BrowserPage() {
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [selectedCode, setSelectedCode] = useState<ICD10Code | null>(null);
  const [error, setError] = useState<string | null>(null);
  const limit = 20;

  const search = useCallback(
    async (searchOffset = 0) => {
      if (!query.trim() || query.trim().length < 2) return;
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `/api/v1/icd10-suggestions/search?q=${encodeURIComponent(query.trim())}&offset=${searchOffset}&limit=${limit}`
        );
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.message || "Search failed");
        }
        const data: SearchResult = await res.json();
        setResult(data);
        setOffset(searchOffset);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Search failed");
      } finally {
        setIsLoading(false);
      }
    },
    [query]
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0);
    search(0);
  };

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/clinical">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Clinical
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">ICD-10-CM Code Browser</h1>
          <p className="text-muted-foreground">
            Search and browse ICD-10-CM diagnosis codes
          </p>
        </div>
      </div>

      {/* Search */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Search by code or description (e.g., 'diabetes', 'E11', 'hypertension')..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={isLoading || query.trim().length < 2}>
              <Search className="h-4 w-4 mr-1" />
              {isLoading ? "Searching..." : "Search"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card className="mb-6 border-red-200">
          <CardContent className="pt-6">
            <p className="text-red-600">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Results List */}
        <div className="lg:col-span-2">
          {result && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">
                    {result.total_results} Results
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={offset === 0}
                      onClick={() => search(Math.max(0, offset - limit))}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      {offset + 1}-{Math.min(offset + limit, result.total_results)}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!result.has_more}
                      onClick={() => search(offset + limit)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {result.codes.map((code) => (
                    <div
                      key={code.code}
                      className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer hover:bg-muted transition-colors ${
                        selectedCode?.code === code.code ? "bg-muted" : ""
                      }`}
                      onClick={() => setSelectedCode(code)}
                    >
                      <code className="font-mono text-sm font-bold min-w-[80px]">
                        {code.code}
                      </code>
                      <span className="flex-1 text-sm">{code.description}</span>
                      <div className="flex items-center gap-2">
                        {code.is_billable && (
                          <Badge variant="default" className="text-xs">
                            Billable
                          </Badge>
                        )}
                        {code.category && (
                          <Badge variant="outline" className="text-xs">
                            {code.category}
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {!result && !isLoading && (
            <Card>
              <CardContent className="pt-12 pb-12 text-center">
                <BookOpen className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">
                  Search for ICD-10-CM codes by description or code prefix
                </p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Code Detail Panel */}
        <div>
          {selectedCode ? (
            <Card className="sticky top-6">
              <CardHeader>
                <CardTitle className="font-mono text-xl">
                  {selectedCode.code}
                </CardTitle>
                <CardDescription>{selectedCode.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">
                    Category
                  </p>
                  <Badge variant="outline">{selectedCode.category || "N/A"}</Badge>
                </div>

                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">
                    Billable
                  </p>
                  <Badge
                    variant={selectedCode.is_billable ? "default" : "secondary"}
                  >
                    {selectedCode.is_billable ? "Yes - Valid for claims" : "No - Requires more specificity"}
                  </Badge>
                </div>

                {selectedCode.parent_code && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">
                      Parent Code
                    </p>
                    <code className="font-mono text-sm">{selectedCode.parent_code}</code>
                  </div>
                )}

                {selectedCode.synonyms.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">
                      Synonyms
                    </p>
                    <div className="space-y-1">
                      {selectedCode.synonyms.map((s, i) => (
                        <p key={i} className="text-sm">{s}</p>
                      ))}
                    </div>
                  </div>
                )}

                <div className="pt-3 border-t">
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <FileText className="h-3 w-3" />
                    Code: {selectedCode.code.replace(".", "")} | Chapter:{" "}
                    {selectedCode.code.charAt(0)}
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="pt-8 pb-8 text-center">
                <Search className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
                <p className="text-sm text-muted-foreground">
                  Select a code to view details
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
