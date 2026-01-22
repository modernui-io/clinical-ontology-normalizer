"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Search,
  BookOpen,
  Database,
  Tag,
  CheckCircle,
  XCircle,
  RefreshCw,
  ArrowRight,
  Filter,
  List,
  FileCode,
  Beaker,
  Activity,
  Heart,
  Users,
  Pill,
} from "lucide-react";

// Types
interface Codelist {
  c_code: string;
  name: string;
  submission_value: string;
  definition: string;
  codelist_type: string;
  domain: string;
  term_count: number;
  version?: string;
}

interface CDISCStats {
  total_codelists: number;
  total_terms: number;
  extensible_codelists: number;
  non_extensible_codelists: number;
  current_version: string;
  available_versions: string[];
  by_domain: Record<string, number>;
}

interface CDISCVersion {
  version: string;
  release_date: string;
  description: string;
  codelist_count: number;
  term_count: number;
  is_current: boolean;
}

interface Domain {
  domain: string;
  description: string;
  codelist_count: number;
  codelists: string[];
}

interface SearchResult {
  query: string;
  search_type: string;
  codelists?: Codelist[];
  codelist_count?: number;
  terms?: Array<{
    term: {
      code: string;
      submission_value: string;
      preferred_term: string;
      synonyms: string[];
    };
    codelist: {
      c_code: string;
      name: string;
      submission_value: string;
    };
  }>;
  term_count?: number;
}

// Domain icons mapping
const domainIcons: Record<string, typeof Users> = {
  DM: Users,
  AE: Activity,
  CM: Pill,
  VS: Heart,
  LB: Beaker,
  DS: FileCode,
  GENERAL: Database,
};

function CDISCBrowserContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // State
  const [stats, setStats] = useState<CDISCStats | null>(null);
  const [versions, setVersions] = useState<CDISCVersion[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [codelists, setCodelists] = useState<Codelist[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);

  const [searchQuery, setSearchQuery] = useState(
    searchParams.get("q") || ""
  );
  const [selectedDomain, setSelectedDomain] = useState<string>(
    searchParams.get("domain") || "all"
  );
  const [selectedVersion, setSelectedVersion] = useState<string>("current");
  const [isLoading, setIsLoading] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Fetch stats, versions, domains, and codelists in parallel
        const [statsRes, versionsRes, domainsRes, codelistsRes] =
          await Promise.all([
            fetch(`/api/cdisc/stats`),
            fetch(`/api/cdisc/versions`),
            fetch(`/api/cdisc/domains`),
            fetch(
              `/api/cdisc/codelists?limit=100${
                selectedDomain !== "all" ? `&domain=${selectedDomain}` : ""
              }`
            ),
          ]);

        if (!statsRes.ok || !versionsRes.ok || !domainsRes.ok || !codelistsRes.ok) {
          throw new Error("Failed to fetch CDISC data");
        }

        const [statsData, versionsData, domainsData, codelistsData] =
          await Promise.all([
            statsRes.json(),
            versionsRes.json(),
            domainsRes.json(),
            codelistsRes.json(),
          ]);

        setStats(statsData);
        setVersions(versionsData.versions);
        setDomains(domainsData.domains);
        setCodelists(codelistsData.items);
      } catch (err) {
        console.error("Error fetching CDISC data:", err);
        setError("Failed to load CDISC terminology. Please try again.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [selectedDomain]);

  // Search function
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }

    setIsSearching(true);
    try {
      const domainParam =
        selectedDomain !== "all" ? `&domain=${selectedDomain}` : "";
      const res = await fetch(
        `/api/cdisc/search?q=${encodeURIComponent(
          searchQuery
        )}&search_type=all${domainParam}&limit=50`
      );

      if (!res.ok) {
        throw new Error("Search failed");
      }

      const data = await res.json();
      setSearchResults(data);

      // Update URL
      const params = new URLSearchParams();
      params.set("q", searchQuery);
      if (selectedDomain !== "all") {
        params.set("domain", selectedDomain);
      }
      router.push(`/cdisc?${params.toString()}`, { scroll: false });
    } catch (err) {
      console.error("Search error:", err);
      setError("Search failed. Please try again.");
    } finally {
      setIsSearching(false);
    }
  }, [searchQuery, selectedDomain, router]);

  // Handle search on Enter key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  // Clear search
  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults(null);
    router.push("/cdisc", { scroll: false });
  };

  // Refresh data
  const refreshData = async () => {
    setIsLoading(true);
    setError(null);
    // Re-fetch by triggering effect
    setSelectedDomain((prev) => prev);
    setIsLoading(false);
  };

  if (error) {
    return (
      <div className="p-6">
        <Card className="border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
          <CardHeader>
            <CardTitle className="text-red-700 dark:text-red-400">
              Error Loading CDISC Terminology
            </CardTitle>
            <CardDescription className="text-red-600 dark:text-red-300">
              {error}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={refreshData} variant="outline">
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-blue-500" />
            CDISC Terminology Browser
          </h1>
          <p className="text-muted-foreground">
            Browse and search CDISC Controlled Terminology for SDTM, ADaM, and
            CDASH
          </p>
        </div>
        <div className="flex gap-2">
          <Select
            value={selectedVersion}
            onValueChange={setSelectedVersion}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select version" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="current">
                Current ({stats?.current_version || "..."})
              </SelectItem>
              {versions
                .filter((v) => !v.is_current)
                .map((v) => (
                  <SelectItem key={v.version} value={v.version}>
                    {v.version}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="icon"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Total Codelists
            </CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : stats?.total_codelists || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              CDISC controlled terminology sets
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Terms</CardTitle>
            <Tag className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : stats?.total_terms || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Individual controlled terms
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Extensible
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {isLoading ? "..." : stats?.extensible_codelists || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Allow sponsor-defined terms
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Non-Extensible
            </CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {isLoading ? "..." : stats?.non_extensible_codelists || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Fixed term sets only
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Search Terminology
          </CardTitle>
          <CardDescription>
            Search across codelists and terms by name, code, or synonym
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search codelists or terms (e.g., SEX, Male, C66731)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="pl-9"
              />
            </div>
            <Select
              value={selectedDomain}
              onValueChange={setSelectedDomain}
            >
              <SelectTrigger className="w-[180px]">
                <Filter className="mr-2 h-4 w-4" />
                <SelectValue placeholder="Filter by domain" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Domains</SelectItem>
                {domains.map((d) => (
                  <SelectItem key={d.domain} value={d.domain}>
                    {d.domain} - {d.description}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={handleSearch} disabled={isSearching}>
              {isSearching ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Search className="mr-2 h-4 w-4" />
              )}
              Search
            </Button>
            {searchResults && (
              <Button variant="outline" onClick={clearSearch}>
                Clear
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Search Results */}
      {searchResults && (
        <Card>
          <CardHeader>
            <CardTitle>
              Search Results for &ldquo;{searchResults.query}&rdquo;
            </CardTitle>
            <CardDescription>
              Found {searchResults.codelist_count || 0} codelists and{" "}
              {searchResults.term_count || 0} terms
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Codelist Results */}
            {searchResults.codelists && searchResults.codelists.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-3">Codelists</h3>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {searchResults.codelists.map((cl) => (
                    <Link
                      key={cl.c_code}
                      href={`/cdisc/codelists/${cl.c_code}`}
                    >
                      <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <Badge variant="outline">{cl.c_code}</Badge>
                            <Badge
                              className={
                                cl.codelist_type === "extensible"
                                  ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                                  : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                              }
                            >
                              {cl.codelist_type}
                            </Badge>
                          </div>
                          <CardTitle className="text-base">
                            {cl.submission_value}
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-0">
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {cl.name}
                          </p>
                          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                            <Badge variant="secondary">{cl.domain}</Badge>
                            <span>{cl.term_count} terms</span>
                          </div>
                        </CardContent>
                      </Card>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Term Results */}
            {searchResults.terms && searchResults.terms.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold mb-3">Terms</h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Term</TableHead>
                      <TableHead>Submission Value</TableHead>
                      <TableHead>Codelist</TableHead>
                      <TableHead>Synonyms</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {searchResults.terms.map((result, idx) => (
                      <TableRow key={`${result.codelist.c_code}-${result.term.code}-${idx}`}>
                        <TableCell className="font-medium">
                          {result.term.preferred_term}
                        </TableCell>
                        <TableCell>
                          <code className="bg-muted px-1.5 py-0.5 rounded text-sm">
                            {result.term.submission_value}
                          </code>
                        </TableCell>
                        <TableCell>
                          <Link
                            href={`/cdisc/codelists/${result.codelist.c_code}`}
                            className="text-blue-600 hover:underline dark:text-blue-400"
                          >
                            {result.codelist.submission_value}
                          </Link>
                        </TableCell>
                        <TableCell className="max-w-[200px]">
                          <span className="text-sm text-muted-foreground truncate">
                            {result.term.synonyms.slice(0, 3).join(", ")}
                            {result.term.synonyms.length > 3 && "..."}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Link
                            href={`/cdisc/codelists/${result.codelist.c_code}`}
                          >
                            <Button variant="ghost" size="sm">
                              <ArrowRight className="h-4 w-4" />
                            </Button>
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {searchResults.codelists?.length === 0 &&
              searchResults.terms?.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  No results found for &ldquo;{searchResults.query}&rdquo;
                </div>
              )}
          </CardContent>
        </Card>
      )}

      {/* Domain Overview and Codelist Grid */}
      {!searchResults && (
        <div className="grid gap-6 lg:grid-cols-4">
          {/* Domains Sidebar */}
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <List className="h-5 w-5" />
                SDTM Domains
              </CardTitle>
              <CardDescription>
                Click to filter by domain
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <button
                  onClick={() => setSelectedDomain("all")}
                  className={`w-full flex items-center justify-between p-2 rounded-lg transition-colors ${
                    selectedDomain === "all"
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    All Domains
                  </span>
                  <Badge variant="secondary">
                    {stats?.total_codelists || 0}
                  </Badge>
                </button>
                {domains
                  .filter((d) => d.codelist_count > 0)
                  .sort((a, b) => b.codelist_count - a.codelist_count)
                  .map((d) => {
                    const Icon = domainIcons[d.domain] || FileCode;
                    return (
                      <button
                        key={d.domain}
                        onClick={() => setSelectedDomain(d.domain)}
                        className={`w-full flex items-center justify-between p-2 rounded-lg transition-colors ${
                          selectedDomain === d.domain
                            ? "bg-primary text-primary-foreground"
                            : "hover:bg-muted"
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <Icon className="h-4 w-4" />
                          <span className="font-medium">{d.domain}</span>
                          <span className="text-xs opacity-70">
                            {d.description}
                          </span>
                        </span>
                        <Badge
                          variant={
                            selectedDomain === d.domain ? "outline" : "secondary"
                          }
                        >
                          {d.codelist_count}
                        </Badge>
                      </button>
                    );
                  })}
              </div>
            </CardContent>
          </Card>

          {/* Codelists Grid */}
          <Card className="lg:col-span-3">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>
                    {selectedDomain === "all"
                      ? "All Codelists"
                      : `${selectedDomain} Domain Codelists`}
                  </CardTitle>
                  <CardDescription>
                    {codelists.length} codelists
                    {selectedDomain !== "all" &&
                      ` in the ${
                        domains.find((d) => d.domain === selectedDomain)
                          ?.description || selectedDomain
                      } domain`}
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : codelists.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  No codelists found
                  {selectedDomain !== "all" && ` for domain ${selectedDomain}`}
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {codelists.map((cl) => (
                    <Link
                      key={cl.c_code}
                      href={`/cdisc/codelists/${cl.c_code}`}
                    >
                      <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <Badge variant="outline" className="font-mono">
                              {cl.c_code}
                            </Badge>
                            <Badge
                              className={
                                cl.codelist_type === "extensible"
                                  ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                                  : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                              }
                            >
                              {cl.codelist_type}
                            </Badge>
                          </div>
                          <CardTitle className="text-lg">
                            {cl.submission_value}
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-0">
                          <p className="text-sm font-medium mb-1">{cl.name}</p>
                          <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                            {cl.definition}
                          </p>
                          <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <Badge variant="secondary">{cl.domain}</Badge>
                            <span>{cl.term_count} terms</span>
                          </div>
                        </CardContent>
                      </Card>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Version Info */}
      <Card>
        <CardHeader>
          <CardTitle>Available Versions</CardTitle>
          <CardDescription>
            CDISC Controlled Terminology release versions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Version</TableHead>
                <TableHead>Release Date</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Codelists</TableHead>
                <TableHead>Terms</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versions.map((v) => (
                <TableRow key={v.version}>
                  <TableCell className="font-mono font-medium">
                    {v.version}
                  </TableCell>
                  <TableCell>
                    {new Date(v.release_date).toLocaleDateString()}
                  </TableCell>
                  <TableCell>{v.description}</TableCell>
                  <TableCell>{v.codelist_count}</TableCell>
                  <TableCell>{v.term_count}</TableCell>
                  <TableCell>
                    {v.is_current ? (
                      <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                        Current
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Previous</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

export default function CDISCBrowserPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center">Loading CDISC Browser...</div>}>
      <CDISCBrowserContent />
    </Suspense>
  );
}
