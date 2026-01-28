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
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  BookOpen,
  Search,
  RefreshCw,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Shield,
  Star,
  Pill,
  Activity,
  Beaker,
  Filter,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface GuidelineSection {
  section_id: string;
  guideline: string;
  section_title: string;
  recommendation_text: string;
  evidence_grade: string;
  recommendation_level: string;
  applies_to_conditions: string[];
  applies_to_medications: string[];
  applies_to_measurements: string[];
  keywords: string[];
}

interface GuidelinesResponse {
  guidelines: GuidelineSection[];
  total: number;
  filters: {
    sources: string[];
    conditions: string[];
    evidence_grades: string[];
  };
}

interface GuidelineStats {
  total_sections: number;
  total_guidelines: number;
  by_source: Record<string, number>;
  by_evidence_grade: Record<string, number>;
  by_recommendation_level: Record<string, number>;
  is_loaded: boolean;
}

interface SearchResult {
  section_id: string;
  guideline: string;
  section_title: string;
  recommendation_text: string;
  evidence_grade: string;
  recommendation_level: string;
  applies_to_conditions: string[];
  score: number;
  match_reasons: string[];
}

// =============================================================================
// Grade Badge
// =============================================================================

function GradeBadge({ grade }: { grade: string }) {
  const styles: Record<string, string> = {
    A: "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300",
    B: "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300",
    C: "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300",
  };

  return (
    <Badge variant="outline" className={`text-xs font-semibold ${styles[grade] || ""}`}>
      Grade {grade}
    </Badge>
  );
}

function RecommendationBadge({ level }: { level: string }) {
  const isStrong = level.toLowerCase() === "strong";
  return (
    <Badge
      variant="outline"
      className={`text-xs ${
        isStrong
          ? "bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-900/30 dark:text-indigo-300"
          : "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300"
      }`}
    >
      {level}
    </Badge>
  );
}

// =============================================================================
// Guideline Card
// =============================================================================

function GuidelineCard({ section }: { section: GuidelineSection }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border rounded-lg bg-white dark:bg-zinc-950">
      <button
        className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="pt-0.5 shrink-0">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{section.section_title}</span>
            <GradeBadge grade={section.evidence_grade} />
            <RecommendationBadge level={section.recommendation_level} />
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {section.guideline}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t">
          <p className="mt-3 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            {section.recommendation_text}
          </p>

          <div className="mt-3 space-y-2">
            {section.applies_to_conditions.length > 0 && (
              <div className="flex items-start gap-2">
                <Activity className="h-3.5 w-3.5 mt-0.5 text-red-500 shrink-0" />
                <div className="flex flex-wrap gap-1">
                  {section.applies_to_conditions.map((c) => (
                    <Badge key={c} variant="secondary" className="text-[10px]">
                      {c}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {section.applies_to_medications.length > 0 && (
              <div className="flex items-start gap-2">
                <Pill className="h-3.5 w-3.5 mt-0.5 text-blue-500 shrink-0" />
                <div className="flex flex-wrap gap-1">
                  {section.applies_to_medications.map((m) => (
                    <Badge key={m} variant="secondary" className="text-[10px]">
                      {m}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {section.applies_to_measurements.length > 0 && (
              <div className="flex items-start gap-2">
                <Beaker className="h-3.5 w-3.5 mt-0.5 text-purple-500 shrink-0" />
                <div className="flex flex-wrap gap-1">
                  {section.applies_to_measurements.map((m) => (
                    <Badge key={m} variant="secondary" className="text-[10px]">
                      {m}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>

          {section.keywords.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {section.keywords.map((kw) => (
                <span
                  key={kw}
                  className="text-[10px] text-muted-foreground bg-zinc-100 dark:bg-zinc-800 rounded px-1.5 py-0.5"
                >
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Search Result Card
// =============================================================================

function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <div className="border rounded-lg p-4 bg-white dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{result.section_title}</span>
            <GradeBadge grade={result.evidence_grade} />
            <RecommendationBadge level={result.recommendation_level} />
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {result.guideline}
          </div>
        </div>
        <Badge
          variant="outline"
          className={`text-xs shrink-0 ${
            result.score >= 0.7
              ? "bg-green-50 text-green-700 border-green-200"
              : result.score >= 0.4
                ? "bg-amber-50 text-amber-700 border-amber-200"
                : "bg-zinc-50 text-zinc-600 border-zinc-200"
          }`}
        >
          {(result.score * 100).toFixed(0)}% match
        </Badge>
      </div>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 line-clamp-4">
        {result.recommendation_text}
      </p>
      {result.match_reasons.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {result.match_reasons.map((reason, i) => (
            <Badge key={i} variant="secondary" className="text-[10px]">
              {reason}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Main Page
// =============================================================================

export default function GuidelinesPage() {
  const [guidelines, setGuidelines] = useState<GuidelineSection[]>([]);
  const [stats, setStats] = useState<GuidelineStats | null>(null);
  const [filters, setFilters] = useState<{
    sources: string[];
    conditions: string[];
    evidence_grades: string[];
  }>({ sources: [], conditions: [], evidence_grades: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [sourceFilter, setSourceFilter] = useState("all");
  const [gradeFilter, setGradeFilter] = useState("all");
  const [conditionFilter, setConditionFilter] = useState("all");

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  const loadGuidelines = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (sourceFilter !== "all") params.set("source", sourceFilter);
      if (gradeFilter !== "all") params.set("evidence_grade", gradeFilter);
      if (conditionFilter !== "all") params.set("condition", conditionFilter);

      const url = `/api/guidelines${params.toString() ? `?${params}` : ""}`;
      const res = await fetch(url);
      if (res.ok) {
        const data: GuidelinesResponse = await res.json();
        setGuidelines(data.guidelines);
        setFilters(data.filters);
      } else {
        setError("Failed to load guidelines");
      }
    } catch {
      setError("Network error loading guidelines");
    } finally {
      setIsLoading(false);
    }
  }, [sourceFilter, gradeFilter, conditionFilter]);

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch("/api/guidelines/stats");
      if (res.ok) {
        setStats(await res.json());
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadGuidelines();
  }, [loadGuidelines]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleSearch = async () => {
    if (searchQuery.length < 3) return;
    setSearching(true);
    setSearched(true);
    try {
      const res = await fetch(`/api/guidelines/search?query=${encodeURIComponent(searchQuery)}&top_k=15`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch {
      // ignore
    } finally {
      setSearching(false);
    }
  };

  const clearSearch = () => {
    setSearchQuery("");
    setSearched(false);
    setSearchResults([]);
  };

  // Group by guideline source
  const grouped = guidelines.reduce<Record<string, GuidelineSection[]>>(
    (acc, section) => {
      if (!acc[section.guideline]) acc[section.guideline] = [];
      acc[section.guideline].push(section);
      return acc;
    },
    {}
  );

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      {/* Header */}
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BookOpen className="h-6 w-6 text-emerald-500" />
              <div>
                <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                  Clinical Guidelines
                </h1>
                <p className="text-sm text-muted-foreground">
                  Evidence-based clinical guidelines for RAG-powered decision support
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {stats && (
                <>
                  <Badge variant="outline" className="text-xs">
                    {stats.total_guidelines} guidelines
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    {stats.total_sections} sections
                  </Badge>
                </>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  loadGuidelines();
                  loadStats();
                }}
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
            {/* Stats Cards */}
            {stats && (
              <div className="grid gap-4 md:grid-cols-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Total Guidelines</CardDescription>
                    <CardTitle className="text-3xl">{stats.total_guidelines}</CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Total Sections</CardDescription>
                    <CardTitle className="text-3xl">{stats.total_sections}</CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Evidence Grade A</CardDescription>
                    <CardTitle className="text-3xl flex items-center gap-2">
                      {stats.by_evidence_grade["A"] || 0}
                      <Star className="h-5 w-5 text-green-500" />
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Strong Recommendations</CardDescription>
                    <CardTitle className="text-3xl flex items-center gap-2">
                      {stats.by_recommendation_level["Strong"] || 0}
                      <Shield className="h-5 w-5 text-indigo-500" />
                    </CardTitle>
                  </CardHeader>
                </Card>
              </div>
            )}

            {/* Search */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Search className="h-4 w-4" />
                  Semantic Search
                </CardTitle>
                <CardDescription>
                  Search clinical guidelines using natural language queries
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  <Input
                    placeholder="e.g., What are the blood pressure targets for diabetic patients?"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  />
                  {searched ? (
                    <Button variant="outline" onClick={clearSearch} className="shrink-0">
                      Clear
                    </Button>
                  ) : null}
                  <Button
                    onClick={handleSearch}
                    disabled={searching || searchQuery.length < 3}
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
                  <div className="mt-4 space-y-2">
                    <p className="text-sm text-muted-foreground">
                      {searchResults.length} results for &ldquo;{searchQuery}&rdquo;
                    </p>
                    {searchResults.map((r) => (
                      <SearchResultCard key={r.section_id} result={r} />
                    ))}
                    {searchResults.length === 0 && (
                      <p className="text-sm text-muted-foreground text-center py-4">
                        No matching guidelines found
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Filters */}
            {!searched && (
              <>
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Filter className="h-4 w-4" />
                      Filters
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-3">
                      <Select value={sourceFilter} onValueChange={setSourceFilter}>
                        <SelectTrigger className="w-72">
                          <SelectValue placeholder="Guideline source" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Sources</SelectItem>
                          {filters.sources.map((s) => (
                            <SelectItem key={s} value={s}>
                              {s}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <Select value={gradeFilter} onValueChange={setGradeFilter}>
                        <SelectTrigger className="w-40">
                          <SelectValue placeholder="Evidence grade" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Grades</SelectItem>
                          {filters.evidence_grades.map((g) => (
                            <SelectItem key={g} value={g}>
                              Grade {g}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <Select value={conditionFilter} onValueChange={setConditionFilter}>
                        <SelectTrigger className="w-52">
                          <SelectValue placeholder="Condition" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Conditions</SelectItem>
                          {filters.conditions.slice(0, 50).map((c) => (
                            <SelectItem key={c} value={c}>
                              {c}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      {(sourceFilter !== "all" ||
                        gradeFilter !== "all" ||
                        conditionFilter !== "all") && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSourceFilter("all");
                            setGradeFilter("all");
                            setConditionFilter("all");
                          }}
                        >
                          Clear filters
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Guidelines List */}
                {isLoading ? (
                  <div className="flex items-center justify-center py-16">
                    <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Showing {guidelines.length} sections across{" "}
                      {Object.keys(grouped).length} guidelines
                    </p>

                    {Object.entries(grouped).map(([source, sections]) => (
                      <Card key={source}>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base flex items-center gap-2">
                            <BookOpen className="h-4 w-4 text-emerald-500" />
                            {source}
                          </CardTitle>
                          <CardDescription>
                            {sections.length} section{sections.length !== 1 ? "s" : ""}
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-1">
                            {sections.map((section) => (
                              <GuidelineCard key={section.section_id} section={section} />
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    ))}

                    {guidelines.length === 0 && (
                      <Card>
                        <CardContent className="py-12 text-center">
                          <BookOpen className="mx-auto h-12 w-12 text-zinc-300 mb-2" />
                          <p className="text-muted-foreground">
                            No guidelines match the current filters
                          </p>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
