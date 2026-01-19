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

// Types
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

// Mock Data
const mockDomains = ["Condition", "Medication", "Procedure", "Observation", "Immunization", "CarePlan", "AllergyIntolerance"];
const mockNoteTypes = ["Progress Note", "Discharge Summary", "H&P", "Consultation", "Lab Report", "Imaging", "Operative Note"];
const mockPatients = [
  { id: "P001", name: "John Smith" },
  { id: "P003", name: "Mary Johnson" },
  { id: "P008", name: "Robert Williams" },
  { id: "P012", name: "Lisa Brown" },
  { id: "P015", name: "David Garcia" },
];

const mockFacetCounts: FacetCounts = {
  domains: {
    Condition: 245,
    Medication: 189,
    Procedure: 134,
    Observation: 456,
    Immunization: 78,
    CarePlan: 45,
    AllergyIntolerance: 92,
  },
  noteTypes: {
    "Progress Note": 520,
    "Discharge Summary": 145,
    "H&P": 89,
    Consultation: 234,
    "Lab Report": 178,
    Imaging: 112,
    "Operative Note": 67,
  },
  patients: {
    P001: { name: "John Smith", count: 156 },
    P003: { name: "Mary Johnson", count: 89 },
    P008: { name: "Robert Williams", count: 234 },
    P012: { name: "Lisa Brown", count: 67 },
    P015: { name: "David Garcia", count: 123 },
  },
  dateRanges: {
    "Last 7 days": 156,
    "Last 30 days": 456,
    "Last 90 days": 789,
    "Last year": 1234,
    "All time": 1567,
  },
};

const mockResults: SearchResult[] = [
  {
    id: "result-001",
    documentId: "doc-123",
    patientId: "P001",
    patientName: "John Smith",
    domain: "Condition",
    content: "Patient presents with Type 2 Diabetes Mellitus with HbA1c of 7.2%. Started on metformin 500mg BID. Will follow up in 3 months for repeat labs.",
    snippet: "...presents with Type 2 **Diabetes** Mellitus with HbA1c of 7.2%...",
    score: 0.95,
    date: "2026-01-15",
    noteType: "Progress Note",
    highlights: ["diabetes", "HbA1c", "metformin"],
    metadata: { provider: "Dr. Sarah Davis", location: "Endocrinology Clinic" },
  },
  {
    id: "result-002",
    documentId: "doc-456",
    patientId: "P003",
    patientName: "Mary Johnson",
    domain: "Medication",
    content: "Review of diabetes medications. Currently on metformin 1000mg BID and glipizide 5mg daily. Good glycemic control achieved.",
    snippet: "...review of **diabetes** medications. Currently on metformin...",
    score: 0.88,
    date: "2026-01-10",
    noteType: "Progress Note",
    highlights: ["diabetes", "metformin", "glipizide"],
    metadata: { provider: "Dr. John Smith", location: "Primary Care" },
  },
  {
    id: "result-003",
    documentId: "doc-789",
    patientId: "P008",
    patientName: "Robert Williams",
    domain: "Observation",
    content: "HbA1c result: 6.8%. Patient has shown excellent improvement in diabetes control with lifestyle modifications and medication adherence.",
    snippet: "...excellent improvement in **diabetes** control with lifestyle...",
    score: 0.82,
    date: "2025-12-20",
    noteType: "Lab Report",
    highlights: ["diabetes", "HbA1c", "improvement"],
    metadata: { provider: "Lab Services", location: "Main Hospital" },
  },
  {
    id: "result-004",
    documentId: "doc-101",
    patientId: "P001",
    patientName: "John Smith",
    domain: "CarePlan",
    content: "Diabetes care plan: Continue current medications, dietary counseling scheduled, foot exam due next visit, eye exam referral placed.",
    snippet: "...**Diabetes** care plan: Continue current medications...",
    score: 0.78,
    date: "2025-12-15",
    noteType: "Progress Note",
    highlights: ["diabetes", "care plan", "medications"],
    metadata: { provider: "Dr. Sarah Davis", location: "Endocrinology Clinic" },
  },
  {
    id: "result-005",
    documentId: "doc-112",
    patientId: "P012",
    patientName: "Lisa Brown",
    domain: "Condition",
    content: "New diagnosis of pre-diabetes based on fasting glucose of 118 mg/dL. Discussed lifestyle modifications and will recheck in 3 months.",
    snippet: "...new diagnosis of pre-**diabetes** based on fasting glucose...",
    score: 0.72,
    date: "2025-11-30",
    noteType: "H&P",
    highlights: ["diabetes", "fasting glucose", "lifestyle"],
    metadata: { provider: "Dr. Michael Chen", location: "Primary Care" },
  },
];

const mockSavedSearches: SavedSearch[] = [
  {
    id: "saved-1",
    name: "Diabetes patients",
    query: "diabetes",
    filters: { domains: ["Condition"], noteTypes: [], patientIds: [], dateFrom: "", dateTo: "" },
    createdAt: "2026-01-10",
  },
  {
    id: "saved-2",
    name: "Recent lab results",
    query: "lab results",
    filters: { domains: [], noteTypes: ["Lab Report"], patientIds: [], dateFrom: "2025-12-01", dateTo: "" },
    createdAt: "2026-01-05",
  },
];

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
  // State
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [facetCounts, setFacetCounts] = useState<FacetCounts>(mockFacetCounts);
  const [totalResults, setTotalResults] = useState(0);
  const [searchTime, setSearchTime] = useState(0);
  const [hasSearched, setHasSearched] = useState(false);

  // Filters
  const [filters, setFilters] = useState<SearchFilters>({
    domains: [],
    noteTypes: [],
    patientIds: [],
    dateFrom: "",
    dateTo: "",
  });
  const [showFilters, setShowFilters] = useState(true);

  // Saved searches
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>(mockSavedSearches);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [searchName, setSearchName] = useState("");

  // Recent searches
  const [recentSearches, setRecentSearches] = useState<string[]>([
    "diabetes medications",
    "blood pressure",
    "recent labs",
  ]);

  // Note: SearchWithDebounce handles auto-focus via its own ref

  // Search function
  const performSearch = useCallback(async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setHasSearched(true);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 500));

    // Filter mock results based on filters
    let filteredResults = mockResults.filter((r) =>
      r.content.toLowerCase().includes(query.toLowerCase())
    );

    if (filters.domains.length > 0) {
      filteredResults = filteredResults.filter((r) =>
        filters.domains.includes(r.domain)
      );
    }
    if (filters.noteTypes.length > 0) {
      filteredResults = filteredResults.filter((r) =>
        filters.noteTypes.includes(r.noteType)
      );
    }
    if (filters.patientIds.length > 0) {
      filteredResults = filteredResults.filter((r) =>
        filters.patientIds.includes(r.patientId)
      );
    }

    setResults(filteredResults);
    setTotalResults(filteredResults.length);
    setSearchTime(Math.random() * 100 + 50);

    // Add to recent searches
    setRecentSearches((prev) => {
      const updated = [query, ...prev.filter((q) => q !== query)].slice(0, 5);
      return updated;
    });

    setIsLoading(false);
  }, [query, filters]);

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
              {mockDomains.map((domain) => (
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
              {mockNoteTypes.map((noteType) => (
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

          {/* Patient Filter */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Patient</h3>
            <div className="space-y-1">
              {mockPatients.map((patient) => (
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
                    const patient = mockPatients.find((p) => p.id === patientId);
                    return (
                      <Badge
                        key={patientId}
                        variant="secondary"
                        className="gap-1 cursor-pointer"
                        onClick={() => toggleFilter("patientIds", patientId)}
                      >
                        {patient?.name || patientId}
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
        {hasSearched && !isLoading && (
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
                            <Badge variant="outline">{result.noteType}</Badge>
                            <div className="flex items-center gap-1 text-sm text-muted-foreground">
                              <User className="h-3 w-3" />
                              <Link
                                href={`/patients/${result.patientId}/graph`}
                                className="hover:underline"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {result.patientName}
                              </Link>
                            </div>
                            <div className="flex items-center gap-1 text-sm text-muted-foreground">
                              <Calendar className="h-3 w-3" />
                              {formatDate(result.date)}
                            </div>
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
                            <Link
                              href={`/documents/${result.documentId}`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Button variant="ghost" size="sm">
                                <ExternalLink className="h-4 w-4" />
                              </Button>
                            </Link>
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
                        {result.metadata && (
                          <div className="flex items-center gap-4 text-xs text-muted-foreground">
                            {result.metadata.provider ? (
                              <span>Provider: {String(result.metadata.provider)}</span>
                            ) : null}
                            {result.metadata.location ? (
                              <span>Location: {String(result.metadata.location)}</span>
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
