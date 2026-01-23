"use client";

import { useState, useCallback, useRef } from "react";
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
import { SearchWithDebounce } from "@/components/SearchWithDebounce";
import {
  ArrowLeft,
  Search,
  Stethoscope,
  ChevronLeft,
  ChevronRight,
  DollarSign,
} from "lucide-react";

interface CPTCode {
  code: string;
  description: string;
  category: string;
  rvu_work: number | null;
  rvu_total: number | null;
}

interface SearchResult {
  query: string;
  total_results: number;
  offset: number;
  limit: number;
  has_more: boolean;
  codes: CPTCode[];
}

export default function CPTBrowserPage() {
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [selectedCode, setSelectedCode] = useState<CPTCode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const currentQuery = useRef("");
  const limit = 20;

  const search = useCallback(
    async (q: string, searchOffset = 0) => {
      if (!q.trim() || q.trim().length < 2) {
        setResult(null);
        return;
      }
      currentQuery.current = q;
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `/api/v1/cpt-suggestions/search?q=${encodeURIComponent(q.trim())}&offset=${searchOffset}&limit=${limit}`
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
    []
  );

  const handleSearch = useCallback((value: string) => {
    setOffset(0);
    search(value, 0);
  }, [search]);

  const categoryColors: Record<string, string> = {
    em: "bg-blue-100 text-blue-800",
    surgery: "bg-red-100 text-red-800",
    radiology: "bg-purple-100 text-purple-800",
    pathology: "bg-green-100 text-green-800",
    medicine: "bg-amber-100 text-amber-800",
    anesthesia: "bg-teal-100 text-teal-800",
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
          <h1 className="text-2xl font-bold">CPT Code Browser</h1>
          <p className="text-muted-foreground">
            Search and browse CPT procedure codes with RVU values
          </p>
        </div>
      </div>

      {/* Search */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <SearchWithDebounce
            onSearch={handleSearch}
            debounceMs={300}
            isLoading={isLoading}
            placeholder="Search by code or description (e.g., '99213', 'arthroscopy', 'colonoscopy')..."
            autoFocus
            size="default"
          />
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
                      onClick={() => search(currentQuery.current, Math.max(0, offset - limit))}
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
                      onClick={() => search(currentQuery.current, offset + limit)}
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
                      <code className="font-mono text-sm font-bold min-w-[60px]">
                        {code.code}
                      </code>
                      <span className="flex-1 text-sm">{code.description}</span>
                      <div className="flex items-center gap-2">
                        {code.rvu_work !== null && (
                          <Badge variant="secondary" className="text-xs">
                            RVU: {code.rvu_work.toFixed(2)}
                          </Badge>
                        )}
                        {code.category && (
                          <Badge
                            className={`text-xs ${categoryColors[code.category.toLowerCase()] || "bg-gray-100 text-gray-800"}`}
                          >
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
                <Stethoscope className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">
                  Search for CPT codes by description or code number
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
                  <Badge
                    className={categoryColors[selectedCode.category?.toLowerCase()] || "bg-gray-100 text-gray-800"}
                  >
                    {selectedCode.category || "N/A"}
                  </Badge>
                </div>

                {selectedCode.rvu_work !== null && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">
                      Work RVU
                    </p>
                    <div className="flex items-center gap-2">
                      <DollarSign className="h-4 w-4 text-green-600" />
                      <span className="font-bold text-lg">
                        {selectedCode.rvu_work.toFixed(2)}
                      </span>
                    </div>
                  </div>
                )}

                <div className="pt-3 border-t">
                  <p className="text-xs text-muted-foreground">
                    Code Range: {selectedCode.code.substring(0, 2)}xxx | Section:{" "}
                    {parseInt(selectedCode.code) < 10000
                      ? "E/M"
                      : parseInt(selectedCode.code) < 70000
                        ? "Surgery"
                        : parseInt(selectedCode.code) < 80000
                          ? "Radiology"
                          : parseInt(selectedCode.code) < 90000
                            ? "Pathology"
                            : "Medicine"}
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
