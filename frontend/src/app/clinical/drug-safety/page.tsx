"use client";

import { useState } from "react";
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
import { Label } from "@/components/ui/label";
import {
  AlertTriangle,
  AlertCircle,
  Pill,
  Search,
  Loader2,
  RefreshCw,
  ShieldCheck,
  ArrowLeft,
  FileText,
  Info,
  CheckCircle2,
} from "lucide-react";

// Types
interface DrugProfile {
  drug_name: string;
  rxcui?: string;
  category?: string;
  warnings?: string[];
  contraindications?: string[];
  adverse_events?: string[];
  black_box_warning?: boolean;
  pregnancy_category?: string;
}

interface DrugSearchResult {
  drug_name: string;
  rxcui?: string;
  category?: string;
  match_score?: number;
}

interface InteractionCheckRequest {
  drugs: string[];
}

interface InteractionCheckResponse {
  interactions: Array<{
    drug1: string;
    drug2: string;
    severity: string;
    description: string;
    management?: string;
  }>;
  summary: {
    total_interactions: number;
    critical_count: number;
    major_count: number;
    moderate_count: number;
  };
}

interface StatsResponse {
  total_profiles: number;
  categories: Record<string, number>;
}

export default function DrugSafetyPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<DrugSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [selectedDrug, setSelectedDrug] = useState<DrugProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [drug1Input, setDrug1Input] = useState("");
  const [drug2Input, setDrug2Input] = useState("");
  const [interactionResult, setInteractionResult] = useState<InteractionCheckResponse | null>(null);
  const [interactionLoading, setInteractionLoading] = useState(false);
  const [interactionError, setInteractionError] = useState<string | null>(null);

  const [stats, setStats] = useState<StatsResponse | null>(null);

  // Fetch stats on mount
  useState(() => {
    fetch("/api/drug-safety/stats")
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch(() => {});
  });

  // Search for drugs
  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    setSearchLoading(true);
    setSearchError(null);

    try {
      const res = await fetch(`/api/drug-safety/search?q=${encodeURIComponent(searchQuery)}`);
      if (!res.ok) {
        throw new Error("Failed to search drugs");
      }
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  };

  // Get drug profile
  const handleGetProfile = async (drugName: string) => {
    setProfileLoading(true);
    setProfileError(null);
    setSelectedDrug(null);

    try {
      const res = await fetch(`/api/drug-safety/profile/${encodeURIComponent(drugName)}`);
      if (!res.ok) {
        throw new Error("Failed to fetch drug profile");
      }
      const data = await res.json();
      setSelectedDrug(data);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to load profile");
    } finally {
      setProfileLoading(false);
    }
  };

  // Check drug interactions
  const handleCheckInteractions = async () => {
    if (!drug1Input.trim() || !drug2Input.trim()) {
      setInteractionError("Please enter both drug names");
      return;
    }

    setInteractionLoading(true);
    setInteractionError(null);
    setInteractionResult(null);

    try {
      const payload: InteractionCheckRequest = {
        drugs: [drug1Input.trim(), drug2Input.trim()],
      };

      const res = await fetch("/api/drug-safety/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error("Failed to check interactions");
      }

      const data = await res.json();
      setInteractionResult(data);
    } catch (err) {
      setInteractionError(err instanceof Error ? err.message : "Interaction check failed");
    } finally {
      setInteractionLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/clinical">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Pill className="h-6 w-6" />
              Drug Safety
            </h1>
            <p className="text-muted-foreground">
              Search drug profiles and check for drug-drug interactions
            </p>
          </div>
        </div>
      </div>

      {/* Stats Card */}
      {stats && stats.total_profiles > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" />
              Database Statistics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold">{stats.total_profiles}</p>
                <p className="text-xs text-muted-foreground">Total Profiles</p>
              </div>
              {Object.entries(stats.categories).slice(0, 3).map(([cat, count]) => (
                <div key={cat} className="text-center">
                  <p className="text-2xl font-bold">{count}</p>
                  <p className="text-xs text-muted-foreground capitalize">{cat}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Drug Search Panel */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Drug Search
            </CardTitle>
            <CardDescription>Search for drug profiles by name</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="search-input">Drug Name</Label>
              <div className="flex gap-2">
                <Input
                  id="search-input"
                  placeholder="e.g., aspirin"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleSearch();
                    }
                  }}
                />
                <Button onClick={handleSearch} disabled={searchLoading}>
                  {searchLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            {searchError && (
              <div className="rounded-md bg-red-50 dark:bg-red-950 p-3 text-sm text-red-600 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{searchError}</span>
              </div>
            )}

            {searchResults.length > 0 && (
              <div className="space-y-2">
                <Label>Search Results ({searchResults.length})</Label>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {searchResults.map((result, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleGetProfile(result.drug_name)}
                      className="w-full text-left p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{result.drug_name}</p>
                          {result.category && (
                            <p className="text-xs text-muted-foreground">{result.category}</p>
                          )}
                        </div>
                        {result.rxcui && (
                          <Badge variant="outline" className="text-xs">
                            {result.rxcui}
                          </Badge>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!searchLoading && searchQuery && searchResults.length === 0 && !searchError && (
              <div className="text-center py-8 text-muted-foreground">
                <Info className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No drugs found matching "{searchQuery}"</p>
              </div>
            )}

            {!searchQuery && (
              <div className="text-center py-8 text-muted-foreground">
                <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">Enter a drug name to search</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Drug Profile Display */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Drug Profile
            </CardTitle>
            <CardDescription>Detailed safety information</CardDescription>
          </CardHeader>
          <CardContent>
            {profileLoading && (
              <div className="text-center py-12">
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
                <p className="text-sm text-muted-foreground mt-2">Loading profile...</p>
              </div>
            )}

            {profileError && (
              <div className="rounded-md bg-red-50 dark:bg-red-950 p-3 text-sm text-red-600 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{profileError}</span>
              </div>
            )}

            {selectedDrug && !profileLoading && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    {selectedDrug.drug_name}
                    {selectedDrug.black_box_warning && (
                      <Badge variant="destructive" className="text-xs">
                        <AlertTriangle className="h-3 w-3 mr-1" />
                        Black Box
                      </Badge>
                    )}
                  </h3>
                  {selectedDrug.category && (
                    <p className="text-sm text-muted-foreground">{selectedDrug.category}</p>
                  )}
                  {selectedDrug.rxcui && (
                    <p className="text-xs text-muted-foreground mt-1">RxCUI: {selectedDrug.rxcui}</p>
                  )}
                </div>

                {selectedDrug.warnings && selectedDrug.warnings.length > 0 && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                      Warnings
                    </Label>
                    <div className="space-y-1">
                      {selectedDrug.warnings.map((warning, idx) => (
                        <div key={idx} className="text-sm p-2 rounded bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800">
                          {warning}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedDrug.contraindications && selectedDrug.contraindications.length > 0 && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 text-red-500" />
                      Contraindications
                    </Label>
                    <div className="space-y-1">
                      {selectedDrug.contraindications.map((ci, idx) => (
                        <div key={idx} className="text-sm p-2 rounded bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800">
                          {ci}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedDrug.adverse_events && selectedDrug.adverse_events.length > 0 && (
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Info className="h-4 w-4 text-blue-500" />
                      Common Adverse Events
                    </Label>
                    <div className="flex flex-wrap gap-2">
                      {selectedDrug.adverse_events.map((ae, idx) => (
                        <Badge key={idx} variant="secondary" className="text-xs">
                          {ae}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {selectedDrug.pregnancy_category && (
                  <div className="space-y-1">
                    <Label>Pregnancy Category</Label>
                    <Badge variant="outline">{selectedDrug.pregnancy_category}</Badge>
                  </div>
                )}
              </div>
            )}

            {!selectedDrug && !profileLoading && !profileError && (
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">Select a drug from search results to view profile</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Interaction Checker */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            Drug Interaction Checker
          </CardTitle>
          <CardDescription>Check for interactions between two drugs</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="drug1">Drug 1</Label>
              <Input
                id="drug1"
                placeholder="e.g., warfarin"
                value={drug1Input}
                onChange={(e) => setDrug1Input(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="drug2">Drug 2</Label>
              <Input
                id="drug2"
                placeholder="e.g., aspirin"
                value={drug2Input}
                onChange={(e) => setDrug2Input(e.target.value)}
              />
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={handleCheckInteractions}
              disabled={interactionLoading || !drug1Input.trim() || !drug2Input.trim()}
              className="flex-1"
            >
              {interactionLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Check Interactions
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setDrug1Input("");
                setDrug2Input("");
                setInteractionResult(null);
                setInteractionError(null);
              }}
            >
              Clear
            </Button>
          </div>

          {interactionError && (
            <div className="rounded-md bg-red-50 dark:bg-red-950 p-3 text-sm text-red-600 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>{interactionError}</span>
            </div>
          )}

          {interactionResult && (
            <div className="space-y-4 pt-4 border-t">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="text-center p-3 rounded-lg bg-muted">
                  <p className="text-xl font-bold">{interactionResult.summary.total_interactions}</p>
                  <p className="text-xs text-muted-foreground">Total</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-950">
                  <p className="text-xl font-bold text-red-600">{interactionResult.summary.critical_count}</p>
                  <p className="text-xs text-muted-foreground">Critical</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-amber-50 dark:bg-amber-950">
                  <p className="text-xl font-bold text-amber-600">{interactionResult.summary.major_count}</p>
                  <p className="text-xs text-muted-foreground">Major</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-blue-50 dark:bg-blue-950">
                  <p className="text-xl font-bold text-blue-600">{interactionResult.summary.moderate_count}</p>
                  <p className="text-xs text-muted-foreground">Moderate</p>
                </div>
              </div>

              {interactionResult.interactions.length > 0 ? (
                <div className="space-y-3">
                  <Label>Interaction Details</Label>
                  {interactionResult.interactions.map((interaction, idx) => {
                    const severityColors = {
                      critical: "border-red-500 bg-red-50 dark:bg-red-950",
                      major: "border-amber-500 bg-amber-50 dark:bg-amber-950",
                      moderate: "border-blue-500 bg-blue-50 dark:bg-blue-950",
                    };
                    const color = severityColors[interaction.severity as keyof typeof severityColors] || "border-gray-200 bg-gray-50";

                    return (
                      <div key={idx} className={`p-4 rounded-lg border ${color}`}>
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="outline" className="capitalize">
                            {interaction.severity}
                          </Badge>
                          <span className="text-sm font-medium">
                            {interaction.drug1} + {interaction.drug2}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">{interaction.description}</p>
                        {interaction.management && (
                          <div className="mt-2 p-2 rounded bg-background border text-sm">
                            <span className="font-medium">Management: </span>
                            {interaction.management}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8">
                  <CheckCircle2 className="h-8 w-8 mx-auto text-green-500 mb-2" />
                  <p className="text-sm font-medium">No interactions found</p>
                  <p className="text-xs text-muted-foreground">
                    No known interactions between {drug1Input} and {drug2Input}
                  </p>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Disclaimer */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-start gap-3 text-xs text-muted-foreground">
            <Info className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Clinical Disclaimer</p>
              <p>
                This drug safety information is for reference purposes only. Always consult
                authoritative clinical resources and use professional judgment when making
                prescribing decisions. This database may not include all possible safety information.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
