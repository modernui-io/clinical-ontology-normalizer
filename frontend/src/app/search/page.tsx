"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { SkeletonCard, SkeletonText } from "@/components/ui/skeleton";
import { SearchWithDebounce } from "@/components/SearchWithDebounce";
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
  Search,
  Filter,
  X,
  Save,
  Clock,
  FileText,
  User,
  Calendar,
  ChevronDown,
  ChevronUp,
  Star,
  Trash,
  BookmarkPlus,
  History,
  Sparkles,
  MessageSquare,
  Loader2,
  AlertCircle,
  ExternalLink,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types -- frontend display model
// ---------------------------------------------------------------------------

interface SearchResult {
  id: string;
  documentId: string;
  patientId: string;
  patientName: string;
  domain: string;
  content: string;
  snippet: string;
  score: number;
  date: string;
  noteType: string;
  highlights: string[];
  metadata: Record<string, unknown>;
}

interface SearchFilters {
  domains: string[];
  noteTypes: string[];
  patientIds: string[];
  dateFrom: string;
  dateTo: string;
}

interface SavedSearch {
  id: string;
  name: string;
  query: string;
  filters: SearchFilters;
  createdAt: string;
}

interface FacetCounts {
  domains: Record<string, number>;
  noteTypes: Record<string, number>;
  patients: Record<string, { name: string; count: number }>;
  dateRanges: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Types -- backend /api/search/typeahead response
// ---------------------------------------------------------------------------

interface TypeaheadResult {
  id: string;
  text: string;
  type: string; // "patient" | "concept" | "document"
  score: number;
  highlight: string | null;
  metadata: Record<string, unknown> | null;
}

interface TypeaheadResponse {
  query: string;
  results: TypeaheadResult[];
  total: number;
  groups: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Static label lists for sidebar (used as fallback when no API data yet)
// ---------------------------------------------------------------------------

const ALL_DOMAINS = [
  "Condition",
  "Medication",
  "Procedure",
  "Observation",
  "Immunization",
  "CarePlan",
  "AllergyIntolerance",
  "Drug",
  "Measurement",
];
const ALL_NOTE_TYPES = [
  "Progress Note",
  "Discharge Summary",
  "H&P",
  "Consultation",
  "Lab Report",
  "Imaging",
  "Operative Note",
];

const EMPTY_FACETS: FacetCounts = {
  domains: {},
  noteTypes: {},
  patients: {},
  dateRanges: {},
};

const INITIAL_SAVED_SEARCHES: SavedSearch[] = [];

// Helper functions
const highlightText = (text: string, query: string): React.ReactNode => {
  if (!query.trim()) return <>{text}</>;

  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const regex = new RegExp(`(${words.join("|")})`, "gi");
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, i) =>
        words.includes(part.toLowerCase()) ? (
          <mark
            key={i}
            className="bg-amber-200 text-amber-900 dark:bg-amber-500/30 dark:text-amber-200 rounded px-0.5"
          >
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </>
  );
};

const getDomainColor = (domain: string): string => {
  const colors: Record<string, string> = {
    Condition: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    Medication: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    Procedure: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
    Observation: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
    Immunization: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
    CarePlan: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    AllergyIntolerance: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
  };
  return colors[domain] || "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
};

const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

export default function SearchPage() {
  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [facetCounts, setFacetCounts] = useState<FacetCounts>(EMPTY_FACETS);
  const [totalResults, setTotalResults] = useState(0);
  const [searchTime, setSearchTime] = useState(0);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Abort controller ref so we can cancel in-flight requests on new searches
  const abortRef = useRef<AbortController | null>(null);

  // Filters
  const [filters, setFilters] = useState<SearchFilters>({
    domains: [],
    noteTypes: [],
    patientIds: [],
    dateFrom: "",
    dateTo: "",
  });
  const [showFilters, setShowFilters] = useState(true);

  // Saved searches (local only -- persisted in component state)
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>(INITIAL_SAVED_SEARCHES);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [searchName, setSearchName] = useState("");

  // Recent searches
  const [recentSearches, setRecentSearches] = useState<string[]>([
    "diabetes medications",
    "blood pressure",
    "recent labs",
  ]);

  // ---------------------------------------------------------------------------
  // Map a backend TypeaheadResult to the frontend SearchResult display model
  // ---------------------------------------------------------------------------
  const mapTypeaheadToSearchResult = useCallback(
    (item: TypeaheadResult, idx: number): SearchResult => {
      const meta = (item.metadata ?? {}) as Record<string, unknown>;
      return {
        id: item.id || `result-${idx}`,
        documentId: item.type === "document" ? item.id : "",
        patientId:
          item.type === "patient"
            ? item.id
            : (meta.patient_id as string) ?? "",
        patientName:
          item.type === "patient"
            ? item.text
            : (meta.patient_name as string) ?? (meta.patient_id as string) ?? "",
        domain: (meta.domain as string) ?? (meta.domain_id as string) ?? item.type,
        content: item.text,
        snippet: item.highlight ?? item.text,
        score: item.score,
        date: (meta.date as string) ?? "",
        noteType: (meta.note_type as string) ?? "",
        highlights: [],
        metadata: meta,
      };
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Build facet counts from the groups dict returned by the typeahead API
  // ---------------------------------------------------------------------------
  const buildFacets = useCallback(
    (groups: Record<string, number>, resultList: SearchResult[]): FacetCounts => {
      const domains: Record<string, number> = {};
      const noteTypes: Record<string, number> = {};
      const patients: Record<string, { name: string; count: number }> = {};

      // Tally from results themselves so the sidebar reflects actual data
      for (const r of resultList) {
        if (r.domain) {
          domains[r.domain] = (domains[r.domain] ?? 0) + 1;
        }
        if (r.noteType) {
          noteTypes[r.noteType] = (noteTypes[r.noteType] ?? 0) + 1;
        }
        if (r.patientId) {
          if (patients[r.patientId]) {
            patients[r.patientId].count += 1;
          } else {
            patients[r.patientId] = {
              name: r.patientName || r.patientId,
              count: 1,
            };
          }
        }
      }

      return {
        domains,
        noteTypes,
        patients,
        dateRanges: groups, // pass raw group counts through
      };
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Core search -- calls GET /api/search/typeahead
  // ---------------------------------------------------------------------------
  const performSearch = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    // Cancel any in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setHasSearched(true);
    setError(null);

    const t0 = performance.now();

    try {
      // Build type filter from selected domain filters
      const typeParam = filters.domains.length > 0
        ? `&types=${filters.domains.map((d) => d.toLowerCase()).join(",")}`
        : "";

      const res = await fetch(
        `/api/search/typeahead?q=${encodeURIComponent(trimmed)}&limit=20${typeParam}`,
        { signal: controller.signal },
      );

      if (!res.ok) {
        throw new Error(`Search failed (${res.status})`);
      }

      const data: TypeaheadResponse = await res.json();
      const elapsed = performance.now() - t0;

      // Map to display model
      let mapped = data.results.map(mapTypeaheadToSearchResult);

      // Apply client-side filters that the typeahead API doesn't support
      if (filters.noteTypes.length > 0) {
        mapped = mapped.filter((r) => filters.noteTypes.includes(r.noteType));
      }
      if (filters.patientIds.length > 0) {
        mapped = mapped.filter((r) => filters.patientIds.includes(r.patientId));
      }

      setResults(mapped);
      setTotalResults(data.total);
      setSearchTime(elapsed);
      setFacetCounts(buildFacets(data.groups, mapped));

      // Track recent searches
      setRecentSearches((prev) => {
        const updated = [trimmed, ...prev.filter((q) => q !== trimmed)].slice(0, 5);
        return updated;
      });
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // Request was cancelled by a newer search -- not an error
        return;
      }
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
      setResults([]);
      setTotalResults(0);
    } finally {
      setIsLoading(false);
    }
  }, [query, filters, mapTypeaheadToSearchResult, buildFacets]);

  // Re-run search when filters change (if we already have a query)
  useEffect(() => {
    if (hasSearched && query.trim()) {
      performSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  // Handle submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    performSearch();
  };

  // Handle filter change
  const toggleFilter = (type: keyof SearchFilters, value: string) => {
    setFilters((prev) => {
      const current = prev[type] as string[];
      const updated = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      return { ...prev, [type]: updated };
    });
  };

  // Clear all filters
  const clearFilters = () => {
    setFilters({
      domains: [],
      noteTypes: [],
      patientIds: [],
      dateFrom: "",
      dateTo: "",
    });
  };

  // Save search
  const handleSaveSearch = () => {
    if (!searchName.trim()) return;

    const newSaved: SavedSearch = {
      id: `saved-${Date.now()}`,
      name: searchName,
      query,
      filters,
      createdAt: new Date().toISOString().split("T")[0],
    };

    setSavedSearches((prev) => [newSaved, ...prev]);
    setSaveDialogOpen(false);
    setSearchName("");
  };

  // Load saved search
  const loadSavedSearch = (saved: SavedSearch) => {
    setQuery(saved.query);
    setFilters(saved.filters);
    setTimeout(performSearch, 100);
  };

  // Delete saved search
  const deleteSavedSearch = (id: string) => {
    setSavedSearches((prev) => prev.filter((s) => s.id !== id));
  };

  const activeFilterCount =
    filters.domains.length +
    filters.noteTypes.length +
    filters.patientIds.length +
    (filters.dateFrom ? 1 : 0) +
    (filters.dateTo ? 1 : 0);

  // ---------------------------------------------------------------------------
  // Derive sidebar filter lists.
  // Before any search we show the static labels; after a search we merge in
  // any new values that appeared in results so the sidebar stays useful.
  // ---------------------------------------------------------------------------
  const domainList = Array.from(
    new Set([...ALL_DOMAINS, ...Object.keys(facetCounts.domains)]),
  );
  const noteTypeList = Array.from(
    new Set([...ALL_NOTE_TYPES, ...Object.keys(facetCounts.noteTypes)]),
  );
  const patientList = Object.entries(facetCounts.patients).map(
    ([id, info]) => ({ id, name: info.name }),
  );

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar - Faceted Filters */}
      {showFilters && (
        <aside className="w-72 border-r bg-muted/30 p-4 space-y-6 overflow-y-auto">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filters
              {activeFilterCount > 0 && (
                <Badge variant="secondary">{activeFilterCount}</Badge>
              )}
            </h2>
            {activeFilterCount > 0 && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear
              </Button>
            )}
          </div>

          {/* Domain Filter */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Domain</h3>
            <div className="space-y-1">
              {domainList.map((domain) => (
                <div key={domain} className="flex items-center space-x-2">
                  <Checkbox
                    id={`domain-${domain}`}
                    checked={filters.domains.includes(domain)}
                    onCheckedChange={() => toggleFilter("domains", domain)}
                  />
                  <Label
                    htmlFor={`domain-${domain}`}
                    className="flex-1 text-sm cursor-pointer flex items-center justify-between"
                  >
                    <span>{domain}</span>
                    <span className="text-xs text-muted-foreground">
                      {facetCounts.domains[domain] || 0}
                    </span>
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* Note Type Filter */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Note Type</h3>
            <div className="space-y-1">
              {noteTypeList.map((noteType) => (
                <div key={noteType} className="flex items-center space-x-2">
                  <Checkbox
                    id={`notetype-${noteType}`}
                    checked={filters.noteTypes.includes(noteType)}
                    onCheckedChange={() => toggleFilter("noteTypes", noteType)}
                  />
                  <Label
                    htmlFor={`notetype-${noteType}`}
                    className="flex-1 text-sm cursor-pointer flex items-center justify-between"
                  >
                    <span>{noteType}</span>
                    <span className="text-xs text-muted-foreground">
                      {facetCounts.noteTypes[noteType] || 0}
                    </span>
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* Patient Filter -- populated dynamically from search results */}
          {patientList.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Patient</h3>
            <div className="space-y-1">
              {patientList.map((patient) => (
                <div key={patient.id} className="flex items-center space-x-2">
                  <Checkbox
                    id={`patient-${patient.id}`}
                    checked={filters.patientIds.includes(patient.id)}
                    onCheckedChange={() => toggleFilter("patientIds", patient.id)}
                  />
                  <Label
                    htmlFor={`patient-${patient.id}`}
                    className="flex-1 text-sm cursor-pointer flex items-center justify-between"
                  >
                    <span>{patient.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {facetCounts.patients[patient.id]?.count || 0}
                    </span>
                  </Label>
                </div>
              ))}
            </div>
          </div>
          )}

          {/* Date Range Filter */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Date Range</h3>
            <div className="grid gap-2">
              <div className="space-y-1">
                <Label htmlFor="date-from" className="text-xs">
                  From
                </Label>
                <Input
                  id="date-from"
                  type="date"
                  value={filters.dateFrom}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, dateFrom: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="date-to" className="text-xs">
                  To
                </Label>
                <Input
                  id="date-to"
                  type="date"
                  value={filters.dateTo}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, dateTo: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
            </div>
          </div>

          {/* Saved Searches */}
          <div className="space-y-2 border-t pt-4">
            <h3 className="text-sm font-medium flex items-center gap-2">
              <Star className="h-4 w-4" />
              Saved Searches
            </h3>
            {savedSearches.length === 0 ? (
              <p className="text-xs text-muted-foreground">No saved searches</p>
            ) : (
              <div className="space-y-1">
                {savedSearches.map((saved) => (
                  <div
                    key={saved.id}
                    className="flex items-center justify-between p-2 rounded-md hover:bg-muted cursor-pointer group"
                    onClick={() => loadSavedSearch(saved)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">
                        {saved.name}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        {saved.query}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="opacity-0 group-hover:opacity-100 h-6 w-6 p-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSavedSearch(saved.id);
                      }}
                    >
                      <Trash className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      )}

      {/* Main Content */}
      <main className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Search className="h-6 w-6" />
              Clinical Search
            </h1>
            <p className="text-muted-foreground">
              Search across clinical documents with faceted filtering
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="mr-2 h-4 w-4" />
            {showFilters ? "Hide Filters" : "Show Filters"}
          </Button>
        </div>

        {/* Search Box */}
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex gap-2">
                <SearchWithDebounce
                  placeholder="Search clinical notes..."
                  value={query}
                  onChange={setQuery}
                  onSearch={performSearch}
                  onSubmit={performSearch}
                  isLoading={isLoading}
                  debounceMs={400}
                  size="lg"
                  containerClassName="flex-1"
                  showShortcut={!query}
                />
                <Button type="submit" disabled={isLoading || !query.trim()}>
                  {isLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="mr-2 h-4 w-4" />
                  )}
                  Search
                </Button>
                {query.trim() && (
                  <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline">
                        <BookmarkPlus className="mr-2 h-4 w-4" />
                        Save
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Save Search</DialogTitle>
                        <DialogDescription>
                          Save this search with current filters for quick access
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="search-name">Search Name</Label>
                          <Input
                            id="search-name"
                            placeholder="My search..."
                            value={searchName}
                            onChange={(e) => setSearchName(e.target.value)}
                          />
                        </div>
                        <div className="p-3 bg-muted rounded-lg">
                          <p className="text-sm">
                            <span className="font-medium">Query:</span> {query}
                          </p>
                          {activeFilterCount > 0 && (
                            <p className="text-sm mt-1">
                              <span className="font-medium">Filters:</span>{" "}
                              {activeFilterCount} active
                            </p>
                          )}
                        </div>
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setSaveDialogOpen(false)}
                        >
                          Cancel
                        </Button>
                        <Button onClick={handleSaveSearch}>Save Search</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                )}
              </div>

              {/* Recent Searches */}
              {!hasSearched && recentSearches.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <History className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Recent:</span>
                  {recentSearches.map((recent, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setQuery(recent);
                        // Focus handled by SearchWithDebounce (Cmd+K)
                      }}
                    >
                      {recent}
                    </Button>
                  ))}
                </div>
              )}

              {/* Active Filters Display */}
              {activeFilterCount > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-muted-foreground">
                    Active filters:
                  </span>
                  {filters.domains.map((domain) => (
                    <Badge
                      key={domain}
                      variant="secondary"
                      className="gap-1 cursor-pointer"
                      onClick={() => toggleFilter("domains", domain)}
                    >
                      {domain}
                      <X className="h-3 w-3" />
                    </Badge>
                  ))}
                  {filters.noteTypes.map((noteType) => (
                    <Badge
                      key={noteType}
                      variant="secondary"
                      className="gap-1 cursor-pointer"
                      onClick={() => toggleFilter("noteTypes", noteType)}
                    >
                      {noteType}
                      <X className="h-3 w-3" />
                    </Badge>
                  ))}
                  {filters.patientIds.map((patientId) => {
                    const patientInfo = facetCounts.patients[patientId];
                    return (
                      <Badge
                        key={patientId}
                        variant="secondary"
                        className="gap-1 cursor-pointer"
                        onClick={() => toggleFilter("patientIds", patientId)}
                      >
                        {patientInfo?.name || patientId}
                        <X className="h-3 w-3" />
                      </Badge>
                    );
                  })}
                  {filters.dateFrom && (
                    <Badge
                      variant="secondary"
                      className="gap-1 cursor-pointer"
                      onClick={() =>
                        setFilters((prev) => ({ ...prev, dateFrom: "" }))
                      }
                    >
                      From: {filters.dateFrom}
                      <X className="h-3 w-3" />
                    </Badge>
                  )}
                  {filters.dateTo && (
                    <Badge
                      variant="secondary"
                      className="gap-1 cursor-pointer"
                      onClick={() =>
                        setFilters((prev) => ({ ...prev, dateTo: "" }))
                      }
                    >
                      To: {filters.dateTo}
                      <X className="h-3 w-3" />
                    </Badge>
                  )}
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        {/* Error State */}
        {error && (
          <Card className="border-destructive">
            <CardContent className="py-6">
              <div className="flex items-center gap-3 text-destructive">
                <AlertCircle className="h-5 w-5 flex-shrink-0" />
                <div>
                  <p className="font-medium">Search failed</p>
                  <p className="text-sm text-muted-foreground">{error}</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="ml-auto"
                  onClick={performSearch}
                >
                  Retry
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Results Loading State */}
        {isLoading && hasSearched && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <SkeletonText lines={1} className="w-48" />
            </div>
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <SkeletonCard key={i} showHeader={false} contentLines={4} />
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        {hasSearched && !isLoading && !error && (
          <div className="space-y-4">
            {/* Results Header */}
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Found <span className="font-medium text-foreground">{totalResults}</span> results
                {searchTime > 0 && (
                  <span className="ml-2">({searchTime.toFixed(1)}ms)</span>
                )}
              </p>
            </div>

            {/* Results List */}
            {results.length > 0 ? (
              <div className="space-y-3">
                {results.map((result) => (
                  <Card
                    key={result.id}
                    className="hover:bg-muted/50 transition-colors cursor-pointer"
                  >
                    <CardContent className="pt-4">
                      <div className="space-y-3">
                        {/* Result Header */}
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge className={getDomainColor(result.domain)}>
                              {result.domain}
                            </Badge>
                            {result.noteType && (
                              <Badge variant="outline">{result.noteType}</Badge>
                            )}
                            {result.patientId && (
                              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                                <User className="h-3 w-3" />
                                <Link
                                  href={`/patients/${result.patientId}/graph`}
                                  className="hover:underline"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  {result.patientName || result.patientId}
                                </Link>
                              </div>
                            )}
                            {result.date && (
                              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                                <Calendar className="h-3 w-3" />
                                {formatDate(result.date)}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={result.score >= 0.8 ? "default" : "secondary"}
                              className={
                                result.score >= 0.8
                                  ? "bg-green-500"
                                  : result.score >= 0.5
                                  ? "bg-amber-500"
                                  : ""
                              }
                            >
                              {(result.score * 100).toFixed(0)}% match
                            </Badge>
                            {result.documentId && (
                              <Link
                                href={`/documents/${result.documentId}`}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <Button variant="ghost" size="sm">
                                  <ExternalLink className="h-4 w-4" />
                                </Button>
                              </Link>
                            )}
                          </div>
                        </div>

                        {/* Result Content */}
                        <p className="text-sm leading-relaxed">
                          {highlightText(result.content, query)}
                        </p>

                        {/* Highlights */}
                        {result.highlights.length > 0 && (
                          <div className="flex items-center gap-2 flex-wrap pt-2 border-t">
                            <span className="text-xs text-muted-foreground">
                              Matched terms:
                            </span>
                            {result.highlights.map((term, i) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                {term}
                              </Badge>
                            ))}
                          </div>
                        )}

                        {/* Metadata */}
                        {result.metadata && Object.keys(result.metadata).length > 0 && (
                          <div className="flex items-center gap-4 text-xs text-muted-foreground">
                            {result.metadata.provider ? (
                              <span>Provider: {String(result.metadata.provider)}</span>
                            ) : null}
                            {result.metadata.location ? (
                              <span>Location: {String(result.metadata.location)}</span>
                            ) : null}
                            {result.metadata.vocabulary ? (
                              <span>Vocab: {String(result.metadata.vocabulary)}</span>
                            ) : null}
                            {result.metadata.vocabulary_id && !result.metadata.vocabulary ? (
                              <span>Vocab: {String(result.metadata.vocabulary_id)}</span>
                            ) : null}
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <Card>
                <CardContent className="py-12">
                  <div className="text-center">
                    <AlertCircle className="mx-auto h-12 w-12 text-muted-foreground/50 mb-4" />
                    <h3 className="text-lg font-medium">No results found</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Try adjusting your search query or filters
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Empty State */}
        {!hasSearched && (
          <Card>
            <CardContent className="py-16">
              <div className="text-center max-w-md mx-auto">
                <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-primary/10 flex items-center justify-center">
                  <Search className="h-8 w-8 text-primary" />
                </div>
                <h2 className="text-xl font-medium mb-2">
                  Search clinical documents
                </h2>
                <p className="text-muted-foreground mb-6">
                  Use natural language to search across patient records. Apply
                  filters to narrow down results by domain, note type, patient, or
                  date range.
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {[
                    "diabetes medications",
                    "hypertension management",
                    "lab results HbA1c",
                  ].map((example, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setQuery(example);
                        // Focus handled by SearchWithDebounce (Cmd+K)
                      }}
                    >
                      <Sparkles className="mr-2 h-3 w-3" />
                      {example}
                    </Button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
