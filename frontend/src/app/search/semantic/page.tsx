"use client";

import { useState, useCallback, useEffect, useRef } from "react";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import {
  Search,
  Filter,
  X,
  Download,
  FileText,
  ArrowLeftRight,
  Network,
  Sparkles,
  Loader2,
  AlertCircle,
  Copy,
  Check,
  Info,
  Layers,
  BookOpen,
  History,
  Star,
} from "lucide-react";

import {
  semanticSearch,
  findSimilarConcepts,
  crosswalkConcept,
  getSearchSuggestions,
  clusterSearchResults,
  getSemanticSearchStats,
  getConceptDetails,
  SemanticSearchResult,
  SemanticSearchResponse,
  CrosswalkMapping,
  ClusterResult,
  SearchSuggestion,
  SemanticSearchStats,
  ConceptDetails,
} from "@/lib/api";

// ============================================================================
// Types
// ============================================================================

interface SavedSearch {
  id: string;
  query: string;
  vocabularies: string[];
  domains: string[];
  timestamp: string;
}

// ============================================================================
// Constants
// ============================================================================

const VOCABULARY_OPTIONS = [
  { value: "ICD10CM", label: "ICD-10-CM", color: "bg-blue-500" },
  { value: "SNOMED", label: "SNOMED CT", color: "bg-purple-500" },
  { value: "RxNorm", label: "RxNorm", color: "bg-green-500" },
  { value: "CPT4", label: "CPT-4", color: "bg-amber-500" },
  { value: "LOINC", label: "LOINC", color: "bg-cyan-500" },
];

const DOMAIN_OPTIONS = [
  { value: "Condition", label: "Conditions", icon: "heart" },
  { value: "Drug", label: "Drugs", icon: "pill" },
  { value: "Procedure", label: "Procedures", icon: "scissors" },
  { value: "Measurement", label: "Measurements", icon: "activity" },
  { value: "Observation", label: "Observations", icon: "eye" },
];

const MATCH_TYPE_COLORS: Record<string, string> = {
  exact: "bg-green-500 text-white",
  synonym: "bg-blue-500 text-white",
  fuzzy: "bg-amber-500 text-white",
  semantic: "bg-purple-500 text-white",
  hierarchy: "bg-cyan-500 text-white",
  crosswalk: "bg-pink-500 text-white",
};

// ============================================================================
// Helper Functions
// ============================================================================

const getVocabularyColor = (vocabId: string): string => {
  const vocab = VOCABULARY_OPTIONS.find((v) => v.value === vocabId);
  return vocab?.color || "bg-gray-500";
};

const formatScore = (score: number): string => {
  return `${(score * 100).toFixed(1)}%`;
};

// ============================================================================
// Components
// ============================================================================

function VocabularyBadge({ vocabulary }: { vocabulary: string }) {
  const vocab = VOCABULARY_OPTIONS.find((v) => v.value === vocabulary);
  return (
    <Badge className={`${getVocabularyColor(vocabulary)} text-white text-xs`}>
      {vocab?.label || vocabulary}
    </Badge>
  );
}

function MatchTypeBadge({ matchType }: { matchType: string }) {
  return (
    <Badge
      variant="outline"
      className={`${MATCH_TYPE_COLORS[matchType] || "bg-gray-500 text-white"} text-xs`}
    >
      {matchType}
    </Badge>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const colorClass =
    score >= 0.8
      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      : score >= 0.5
      ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
      : "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";

  return <Badge className={colorClass}>{formatScore(score)}</Badge>;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={handleCopy}>
      {copied ? (
        <Check className="h-3 w-3 text-green-500" />
      ) : (
        <Copy className="h-3 w-3" />
      )}
    </Button>
  );
}

function SearchResultCard({
  result,
  onFindSimilar,
  onShowCrosswalk,
  onViewDetails,
}: {
  result: SemanticSearchResult;
  onFindSimilar: (conceptId: number) => void;
  onShowCrosswalk: (conceptId: number) => void;
  onViewDetails: (conceptId: number) => void;
}) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="pt-4">
        <div className="space-y-3">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <VocabularyBadge vocabulary={result.vocabulary_id} />
                <Badge variant="outline" className="text-xs">
                  {result.domain_id}
                </Badge>
                <MatchTypeBadge matchType={result.match_type} />
                <ScoreBadge score={result.score} />
              </div>
              <h3 className="font-semibold text-lg">{result.concept_name}</h3>
              <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                <span className="font-mono">{result.concept_code}</span>
                <CopyButton text={result.concept_code} />
                <span>|</span>
                <span>ID: {result.concept_id}</span>
                <CopyButton text={result.concept_id.toString()} />
              </div>
            </div>
          </div>

          {/* Explanation */}
          {result.explanation && (
            <p className="text-sm text-muted-foreground italic">
              {result.explanation}
            </p>
          )}

          {/* Synonyms */}
          {result.synonyms && result.synonyms.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                Synonyms:
              </span>
              <div className="flex flex-wrap gap-1">
                {result.synonyms.slice(0, 5).map((syn, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {syn}
                  </Badge>
                ))}
                {result.synonyms.length > 5 && (
                  <Badge variant="outline" className="text-xs">
                    +{result.synonyms.length - 5} more
                  </Badge>
                )}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onFindSimilar(result.concept_id)}
            >
              <Network className="mr-1 h-3 w-3" />
              Similar
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onShowCrosswalk(result.concept_id)}
            >
              <ArrowLeftRight className="mr-1 h-3 w-3" />
              Crosswalk
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onViewDetails(result.concept_id)}
            >
              <Info className="mr-1 h-3 w-3" />
              Details
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SimilarConceptsPanel({
  conceptId,
  conceptName,
  onClose,
}: {
  conceptId: number;
  conceptName: string;
  onClose: () => void;
}) {
  const [results, setResults] = useState<SemanticSearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSimilar = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await findSimilarConcepts({
          concept_id: conceptId,
          top_k: 10,
          threshold: 0.5,
        });
        setResults(response.results);
      } catch {
        setError("Failed to load similar concepts");
      } finally {
        setLoading(false);
      }
    };
    fetchSimilar();
  }, [conceptId]);

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm">Similar Concepts</CardTitle>
            <CardDescription className="text-xs truncate max-w-[200px]">
              {conceptName}
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px]">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center text-sm text-muted-foreground">
              {error}
            </div>
          ) : results.length === 0 ? (
            <div className="text-center text-sm text-muted-foreground">
              No similar concepts found
            </div>
          ) : (
            <div className="space-y-2">
              {results.map((result) => (
                <div
                  key={result.concept_id}
                  className="p-2 rounded border hover:bg-muted/50"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <VocabularyBadge vocabulary={result.vocabulary_id} />
                    <ScoreBadge score={result.score} />
                  </div>
                  <p className="text-sm font-medium">{result.concept_name}</p>
                  <p className="text-xs text-muted-foreground font-mono">
                    {result.concept_code}
                  </p>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function CrosswalkPanel({
  conceptId,
  conceptName,
  sourceVocab,
  onClose,
}: {
  conceptId: number;
  conceptName: string;
  sourceVocab: string;
  onClose: () => void;
}) {
  const [selectedTarget, setSelectedTarget] = useState<string>("SNOMED");
  const [mappings, setMappings] = useState<CrosswalkMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCrosswalk = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await crosswalkConcept({
        concept_id: conceptId,
        target_vocabulary: selectedTarget,
      });
      setMappings(response.mappings);
    } catch {
      setError("Failed to load crosswalk mappings");
    } finally {
      setLoading(false);
    }
  }, [conceptId, selectedTarget]);

  useEffect(() => {
    fetchCrosswalk();
  }, [fetchCrosswalk]);

  const availableTargets = VOCABULARY_OPTIONS.filter(
    (v) => v.value !== sourceVocab
  );

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm">Vocabulary Crosswalk</CardTitle>
            <CardDescription className="text-xs truncate max-w-[200px]">
              {conceptName}
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <VocabularyBadge vocabulary={sourceVocab} />
            <ArrowLeftRight className="h-4 w-4" />
            <Select value={selectedTarget} onValueChange={setSelectedTarget}>
              <SelectTrigger className="w-[140px] h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {availableTargets.map((v) => (
                  <SelectItem key={v.value} value={v.value}>
                    {v.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <ScrollArea className="h-[350px]">
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : error ? (
              <div className="text-center text-sm text-muted-foreground">
                {error}
              </div>
            ) : mappings.length === 0 ? (
              <div className="text-center text-sm text-muted-foreground">
                No mappings found to {selectedTarget}
              </div>
            ) : (
              <div className="space-y-2">
                {mappings.map((mapping, i) => (
                  <div key={i} className="p-2 rounded border hover:bg-muted/50">
                    <div className="flex items-center gap-2 mb-1">
                      <VocabularyBadge vocabulary={mapping.target_vocabulary} />
                      <Badge
                        variant="outline"
                        className={
                          mapping.mapping_type === "direct"
                            ? "bg-green-100 text-green-800"
                            : "bg-amber-100 text-amber-800"
                        }
                      >
                        {mapping.mapping_type}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {(mapping.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-sm font-medium">{mapping.target_name}</p>
                    <div className="flex items-center gap-1 mt-1">
                      <p className="text-xs text-muted-foreground font-mono">
                        {mapping.target_code}
                      </p>
                      <CopyButton text={mapping.target_code} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
}

function ConceptDetailsPanel({
  conceptId,
  onClose,
}: {
  conceptId: number;
  onClose: () => void;
}) {
  const [concept, setConcept] = useState<ConceptDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      setError(null);
      try {
        const details = await getConceptDetails(conceptId);
        setConcept(details);
      } catch {
        setError("Failed to load concept details");
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [conceptId]);

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Concept Details</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px]">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center text-sm text-muted-foreground">
              {error}
            </div>
          ) : concept ? (
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold">{concept.concept_name}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <VocabularyBadge vocabulary={concept.vocabulary_id} />
                  <Badge variant="outline">{concept.domain_id}</Badge>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Code:</span>
                  <span className="ml-2 font-mono">{concept.concept_code}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">ID:</span>
                  <span className="ml-2">{concept.concept_id}</span>
                </div>
                {concept.concept_class_id && (
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Class:</span>
                    <span className="ml-2">{concept.concept_class_id}</span>
                  </div>
                )}
                {concept.semantic_type && (
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Semantic Type:</span>
                    <span className="ml-2">{concept.semantic_type}</span>
                  </div>
                )}
              </div>

              {concept.synonyms && concept.synonyms.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">Synonyms</h4>
                  <div className="flex flex-wrap gap-1">
                    {concept.synonyms.map((syn, i) => (
                      <Badge key={i} variant="secondary" className="text-xs">
                        {syn}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {concept.parents && concept.parents.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">
                    Parent Concepts ({concept.parents.length})
                  </h4>
                  <div className="text-xs text-muted-foreground">
                    {concept.parents.slice(0, 5).join(", ")}
                    {concept.parents.length > 5 && ` +${concept.parents.length - 5} more`}
                  </div>
                </div>
              )}

              {concept.children && concept.children.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">
                    Child Concepts ({concept.children.length})
                  </h4>
                  <div className="text-xs text-muted-foreground">
                    {concept.children.slice(0, 5).join(", ")}
                    {concept.children.length > 5 && ` +${concept.children.length - 5} more`}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function ClusteredResultsView({
  clusters,
  onFindSimilar,
  onShowCrosswalk,
  onViewDetails,
}: {
  clusters: ClusterResult[];
  onFindSimilar: (conceptId: number) => void;
  onShowCrosswalk: (conceptId: number) => void;
  onViewDetails: (conceptId: number) => void;
}) {
  return (
    <div className="space-y-6">
      {clusters.map((cluster) => (
        <div key={cluster.cluster_id}>
          <div className="flex items-center gap-2 mb-3">
            <Layers className="h-4 w-4" />
            <h3 className="font-semibold">{cluster.cluster_name}</h3>
            <Badge variant="secondary">{cluster.total_count} results</Badge>
          </div>
          <div className="space-y-3 pl-6">
            {cluster.results.map((result) => (
              <SearchResultCard
                key={result.concept_id}
                result={result}
                onFindSimilar={onFindSimilar}
                onShowCrosswalk={onShowCrosswalk}
                onViewDetails={onViewDetails}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function SemanticSearchPage() {
  // Search state
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [searchResponse, setSearchResponse] = useState<SemanticSearchResponse | null>(null);
  const [clusters, setClusters] = useState<ClusterResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedVocabularies, setSelectedVocabularies] = useState<string[]>([]);
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [threshold, setThreshold] = useState([0.3]);
  const [includeFuzzy, setIncludeFuzzy] = useState(true);
  const [expandQuery, setExpandQuery] = useState(true);
  const [topK, setTopK] = useState(20);

  // UI state
  const [showFilters, setShowFilters] = useState(true);
  const [viewMode, setViewMode] = useState<"list" | "cluster" | "table">("list");
  const [selectedConcept, setSelectedConcept] = useState<{
    id: number;
    name: string;
    vocab: string;
  } | null>(null);
  const [sidePanel, setSidePanel] = useState<"similar" | "crosswalk" | "details" | null>(null);

  // Suggestions
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Saved searches
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  // Stats
  const [stats, setStats] = useState<SemanticSearchStats | null>(null);

  // Load stats on mount
  useEffect(() => {
    getSemanticSearchStats()
      .then(setStats)
      .catch(() => {});
  }, []);

  // Fetch suggestions as user types
  useEffect(() => {
    const fetchSuggestions = async () => {
      if (query.length < 2) {
        setSuggestions([]);
        return;
      }
      try {
        const response = await getSearchSuggestions(
          query,
          selectedVocabularies.length > 0 ? selectedVocabularies : undefined,
          10
        );
        setSuggestions(response.suggestions);
      } catch {
        setSuggestions([]);
      }
    };

    const debounceTimer = setTimeout(fetchSuggestions, 200);
    return () => clearTimeout(debounceTimer);
  }, [query, selectedVocabularies]);

  // Search handler
  const performSearch = useCallback(async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);
    setShowSuggestions(false);

    try {
      const response = await semanticSearch({
        query: query.trim(),
        vocabularies: selectedVocabularies.length > 0 ? selectedVocabularies : undefined,
        domains: selectedDomains.length > 0 ? selectedDomains : undefined,
        top_k: topK,
        threshold: threshold[0],
        include_fuzzy: includeFuzzy,
        expand_query: expandQuery,
      });

      setSearchResponse(response);

      // Also cluster results
      if (response.results.length > 0) {
        try {
          const clusterResponse = await clusterSearchResults(response.results);
          setClusters(clusterResponse.clusters);
        } catch {
          setClusters([]);
        }
      } else {
        setClusters([]);
      }

      // Add to recent searches
      setRecentSearches((prev) => {
        const updated = [query, ...prev.filter((q) => q !== query)].slice(0, 5);
        return updated;
      });
    } catch {
      setError("Search failed. Please try again.");
      setSearchResponse(null);
      setClusters([]);
    } finally {
      setIsLoading(false);
    }
  }, [
    query,
    selectedVocabularies,
    selectedDomains,
    topK,
    threshold,
    includeFuzzy,
    expandQuery,
  ]);

  // Handle form submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    performSearch();
  };

  // Toggle vocabulary filter
  const toggleVocabulary = (vocab: string) => {
    setSelectedVocabularies((prev) =>
      prev.includes(vocab) ? prev.filter((v) => v !== vocab) : [...prev, vocab]
    );
  };

  // Toggle domain filter
  const toggleDomain = (domain: string) => {
    setSelectedDomains((prev) =>
      prev.includes(domain) ? prev.filter((d) => d !== domain) : [...prev, domain]
    );
  };

  // Export results
  const exportResults = (format: "csv" | "json") => {
    if (!searchResponse?.results) return;

    const data = searchResponse.results.map((r) => ({
      concept_id: r.concept_id,
      concept_code: r.concept_code,
      concept_name: r.concept_name,
      vocabulary: r.vocabulary_id,
      domain: r.domain_id,
      score: r.score,
      match_type: r.match_type,
    }));

    let content: string;
    let filename: string;
    let mimeType: string;

    if (format === "json") {
      content = JSON.stringify(data, null, 2);
      filename = `semantic_search_${query.replace(/\s+/g, "_")}.json`;
      mimeType = "application/json";
    } else {
      const headers = Object.keys(data[0]).join(",");
      const rows = data.map((row) => Object.values(row).join(","));
      content = [headers, ...rows].join("\n");
      filename = `semantic_search_${query.replace(/\s+/g, "_")}.csv`;
      mimeType = "text/csv";
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Save current search
  const saveSearch = () => {
    const newSearch: SavedSearch = {
      id: `search-${Date.now()}`,
      query,
      vocabularies: selectedVocabularies,
      domains: selectedDomains,
      timestamp: new Date().toISOString(),
    };
    setSavedSearches((prev) => [newSearch, ...prev.slice(0, 9)]);
  };

  // Load saved search
  const loadSavedSearch = (search: SavedSearch) => {
    setQuery(search.query);
    setSelectedVocabularies(search.vocabularies);
    setSelectedDomains(search.domains);
  };

  // Handle side panel actions
  const handleFindSimilar = (conceptId: number) => {
    const concept = searchResponse?.results.find((r) => r.concept_id === conceptId);
    if (concept) {
      setSelectedConcept({
        id: conceptId,
        name: concept.concept_name,
        vocab: concept.vocabulary_id,
      });
      setSidePanel("similar");
    }
  };

  const handleShowCrosswalk = (conceptId: number) => {
    const concept = searchResponse?.results.find((r) => r.concept_id === conceptId);
    if (concept) {
      setSelectedConcept({
        id: conceptId,
        name: concept.concept_name,
        vocab: concept.vocabulary_id,
      });
      setSidePanel("crosswalk");
    }
  };

  const handleViewDetails = (conceptId: number) => {
    const concept = searchResponse?.results.find((r) => r.concept_id === conceptId);
    if (concept) {
      setSelectedConcept({
        id: conceptId,
        name: concept.concept_name,
        vocab: concept.vocabulary_id,
      });
      setSidePanel("details");
    }
  };

  const closeSidePanel = () => {
    setSidePanel(null);
    setSelectedConcept(null);
  };

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar - Filters */}
      {showFilters && (
        <aside className="w-72 border-r bg-muted/30 p-4 space-y-6 overflow-y-auto">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Search Filters
            </h2>
          </div>

          {/* Vocabulary Filter */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Vocabularies</h3>
            <div className="space-y-1">
              {VOCABULARY_OPTIONS.map((vocab) => (
                <div key={vocab.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={`vocab-${vocab.value}`}
                    checked={selectedVocabularies.includes(vocab.value)}
                    onCheckedChange={() => toggleVocabulary(vocab.value)}
                  />
                  <Label
                    htmlFor={`vocab-${vocab.value}`}
                    className="flex-1 text-sm cursor-pointer flex items-center gap-2"
                  >
                    <span className={`w-2 h-2 rounded-full ${vocab.color}`} />
                    {vocab.label}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* Domain Filter */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Clinical Domains</h3>
            <div className="space-y-1">
              {DOMAIN_OPTIONS.map((domain) => (
                <div key={domain.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={`domain-${domain.value}`}
                    checked={selectedDomains.includes(domain.value)}
                    onCheckedChange={() => toggleDomain(domain.value)}
                  />
                  <Label
                    htmlFor={`domain-${domain.value}`}
                    className="flex-1 text-sm cursor-pointer"
                  >
                    {domain.label}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* Threshold Slider */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Min Score</h3>
              <span className="text-sm text-muted-foreground">
                {(threshold[0] * 100).toFixed(0)}%
              </span>
            </div>
            <Slider
              value={threshold}
              onValueChange={setThreshold}
              min={0}
              max={1}
              step={0.1}
            />
          </div>

          {/* Max Results */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Max Results</h3>
            <Select
              value={topK.toString()}
              onValueChange={(v) => setTopK(parseInt(v))}
            >
              <SelectTrigger className="h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[10, 20, 50, 100].map((n) => (
                  <SelectItem key={n} value={n.toString()}>
                    {n} results
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Options */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Search Options</h3>
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="fuzzy"
                  checked={includeFuzzy}
                  onCheckedChange={(c) => setIncludeFuzzy(c === true)}
                />
                <Label htmlFor="fuzzy" className="text-sm cursor-pointer">
                  Include fuzzy matches
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="expand"
                  checked={expandQuery}
                  onCheckedChange={(c) => setExpandQuery(c === true)}
                />
                <Label htmlFor="expand" className="text-sm cursor-pointer">
                  Expand abbreviations
                </Label>
              </div>
            </div>
          </div>

          <Separator />

          {/* Saved Searches */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium flex items-center gap-2">
              <Star className="h-4 w-4" />
              Saved Searches
            </h3>
            {savedSearches.length === 0 ? (
              <p className="text-xs text-muted-foreground">No saved searches</p>
            ) : (
              <div className="space-y-1">
                {savedSearches.slice(0, 5).map((search) => (
                  <Button
                    key={search.id}
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start text-xs"
                    onClick={() => loadSavedSearch(search)}
                  >
                    {search.query}
                  </Button>
                ))}
              </div>
            )}
          </div>

          {/* Stats */}
          {stats && (
            <div className="pt-4 border-t">
              <h3 className="text-sm font-medium mb-2">Index Statistics</h3>
              <div className="text-xs text-muted-foreground space-y-1">
                <div>Total Concepts: {stats.total_concepts.toLocaleString()}</div>
                <div>Unique Codes: {stats.unique_codes.toLocaleString()}</div>
                <div>Indexed Synonyms: {stats.indexed_synonyms.toLocaleString()}</div>
              </div>
            </div>
          )}
        </aside>
      )}

      {/* Main Content */}
      <main className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Sparkles className="h-6 w-6" />
              Semantic Terminology Search
            </h1>
            <p className="text-muted-foreground">
              Search across ICD-10, SNOMED CT, RxNorm, CPT, and LOINC with natural language
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
              <div className="relative">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      ref={searchInputRef}
                      placeholder='Search clinical terminologies (e.g., "heart failure", "diabetes medications", "E11.9")'
                      value={query}
                      onChange={(e) => {
                        setQuery(e.target.value);
                        setShowSuggestions(true);
                      }}
                      onFocus={() => setShowSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                      className="pl-10 h-12 text-lg"
                    />

                    {/* Autocomplete Suggestions */}
                    {showSuggestions && suggestions.length > 0 && (
                      <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-background border rounded-md shadow-lg max-h-64 overflow-y-auto">
                        {suggestions.map((suggestion) => (
                          <button
                            key={suggestion.concept_id}
                            type="button"
                            className="w-full px-3 py-2 text-left hover:bg-muted flex items-center gap-2"
                            onClick={() => {
                              setQuery(suggestion.concept_name);
                              setShowSuggestions(false);
                            }}
                          >
                            <VocabularyBadge vocabulary={suggestion.vocabulary_id} />
                            <span className="flex-1 truncate">
                              {suggestion.display}
                            </span>
                            <span className="text-xs text-muted-foreground font-mono">
                              {suggestion.concept_code}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button
                    type="submit"
                    size="lg"
                    disabled={isLoading || !query.trim()}
                  >
                    {isLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Search className="mr-2 h-4 w-4" />
                    )}
                    Search
                  </Button>
                  {query.trim() && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="outline"
                            size="lg"
                            onClick={saveSearch}
                          >
                            <Star className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Save search</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
              </div>

              {/* Active Filters */}
              {(selectedVocabularies.length > 0 || selectedDomains.length > 0) && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-muted-foreground">Filters:</span>
                  {selectedVocabularies.map((vocab) => (
                    <Badge
                      key={vocab}
                      variant="secondary"
                      className="gap-1 cursor-pointer"
                      onClick={() => toggleVocabulary(vocab)}
                    >
                      {VOCABULARY_OPTIONS.find((v) => v.value === vocab)?.label}
                      <X className="h-3 w-3" />
                    </Badge>
                  ))}
                  {selectedDomains.map((domain) => (
                    <Badge
                      key={domain}
                      variant="secondary"
                      className="gap-1 cursor-pointer"
                      onClick={() => toggleDomain(domain)}
                    >
                      {DOMAIN_OPTIONS.find((d) => d.value === domain)?.label}
                      <X className="h-3 w-3" />
                    </Badge>
                  ))}
                </div>
              )}

              {/* Recent Searches */}
              {!searchResponse && recentSearches.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <History className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Recent:</span>
                  {recentSearches.map((recent, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      size="sm"
                      onClick={() => setQuery(recent)}
                    >
                      {recent}
                    </Button>
                  ))}
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        {/* Error State */}
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-destructive">
                <AlertCircle className="h-5 w-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Results */}
        {searchResponse && (
          <div className="flex gap-6">
            {/* Results Panel */}
            <div className="flex-1 space-y-4">
              {/* Results Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <p className="text-sm text-muted-foreground">
                    Found{" "}
                    <span className="font-medium text-foreground">
                      {searchResponse.total}
                    </span>{" "}
                    results in {searchResponse.search_time_ms.toFixed(1)}ms
                  </p>
                  {searchResponse.expanded_queries.length > 1 && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger>
                          <Badge variant="outline" className="gap-1">
                            <Sparkles className="h-3 w-3" />
                            Query expanded
                          </Badge>
                        </TooltipTrigger>
                        <TooltipContent>
                          <div className="text-xs">
                            Searched for: {searchResponse.expanded_queries.join(", ")}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as typeof viewMode)}>
                    <TabsList>
                      <TabsTrigger value="list">List</TabsTrigger>
                      <TabsTrigger value="cluster">Clustered</TabsTrigger>
                      <TabsTrigger value="table">Table</TabsTrigger>
                    </TabsList>
                  </Tabs>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => exportResults("csv")}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Export as CSV</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => exportResults("json")}
                        >
                          <FileText className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Export as JSON</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </div>

              {/* Results Content */}
              {searchResponse.results.length === 0 ? (
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
              ) : viewMode === "list" ? (
                <div className="space-y-3">
                  {searchResponse.results.map((result) => (
                    <SearchResultCard
                      key={result.concept_id}
                      result={result}
                      onFindSimilar={handleFindSimilar}
                      onShowCrosswalk={handleShowCrosswalk}
                      onViewDetails={handleViewDetails}
                    />
                  ))}
                </div>
              ) : viewMode === "cluster" ? (
                <ClusteredResultsView
                  clusters={clusters}
                  onFindSimilar={handleFindSimilar}
                  onShowCrosswalk={handleShowCrosswalk}
                  onViewDetails={handleViewDetails}
                />
              ) : (
                <Card>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Code</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Vocabulary</TableHead>
                        <TableHead>Domain</TableHead>
                        <TableHead>Match</TableHead>
                        <TableHead className="text-right">Score</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {searchResponse.results.map((result) => (
                        <TableRow
                          key={result.concept_id}
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => handleViewDetails(result.concept_id)}
                        >
                          <TableCell className="font-mono text-sm">
                            {result.concept_code}
                          </TableCell>
                          <TableCell className="max-w-[300px] truncate">
                            {result.concept_name}
                          </TableCell>
                          <TableCell>
                            <VocabularyBadge vocabulary={result.vocabulary_id} />
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{result.domain_id}</Badge>
                          </TableCell>
                          <TableCell>
                            <MatchTypeBadge matchType={result.match_type} />
                          </TableCell>
                          <TableCell className="text-right">
                            <ScoreBadge score={result.score} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Card>
              )}
            </div>

            {/* Side Panel */}
            {sidePanel && selectedConcept && (
              <div className="w-80 shrink-0">
                {sidePanel === "similar" && (
                  <SimilarConceptsPanel
                    conceptId={selectedConcept.id}
                    conceptName={selectedConcept.name}
                    onClose={closeSidePanel}
                  />
                )}
                {sidePanel === "crosswalk" && (
                  <CrosswalkPanel
                    conceptId={selectedConcept.id}
                    conceptName={selectedConcept.name}
                    sourceVocab={selectedConcept.vocab}
                    onClose={closeSidePanel}
                  />
                )}
                {sidePanel === "details" && (
                  <ConceptDetailsPanel
                    conceptId={selectedConcept.id}
                    onClose={closeSidePanel}
                  />
                )}
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!searchResponse && !isLoading && (
          <Card>
            <CardContent className="py-16">
              <div className="text-center max-w-lg mx-auto">
                <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-primary/10 flex items-center justify-center">
                  <BookOpen className="h-8 w-8 text-primary" />
                </div>
                <h2 className="text-xl font-medium mb-2">
                  Semantic Terminology Search
                </h2>
                <p className="text-muted-foreground mb-6">
                  Search across multiple clinical vocabularies using natural language.
                  Find exact matches, synonyms, and semantically similar concepts.
                  Map between ICD-10, SNOMED CT, RxNorm, CPT, and LOINC.
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {[
                    "heart failure",
                    "diabetes medications",
                    "E11.9",
                    "blood pressure",
                    "chest pain",
                  ].map((example, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      size="sm"
                      onClick={() => setQuery(example)}
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
