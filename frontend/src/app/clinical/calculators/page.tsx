"use client";

import { useState, useMemo, useEffect } from "react";
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
  Calculator,
  Search,
  ArrowLeft,
  Heart,
  Activity,
  Stethoscope,
  Brain,
  Droplets,
  Scale,
  FlaskConical,
  Star,
  StarOff,
  RefreshCw,
  TrendingUp,
  Gauge,
} from "lucide-react";

// Types matching backend
interface CalculatorSummary {
  id: string;
  name: string;
  short_name: string;
  category: string;
  description: string;
  calc_type?: string; // For data-driven calculators
}

interface CategoryInfo {
  id: string;
  name: string;
  count: number;
}

interface CalculatorsResponse {
  calculators: CalculatorSummary[];
  total_count: number;
  categories: CategoryInfo[];
}

interface DataDrivenCalculatorsResponse {
  calculators: CalculatorSummary[];
  total_count: number;
}

// Fallback data in case API is unavailable
const fallbackCalculators: CalculatorSummary[] = [
  { id: "ascvd", name: "ASCVD 10-Year Risk", short_name: "ASCVD", category: "cardiovascular", description: "10-year atherosclerotic cardiovascular disease risk using Pooled Cohort Equations" },
  { id: "heart", name: "HEART Score", short_name: "HEART", category: "cardiovascular", description: "Major adverse cardiac event risk for chest pain patients" },
  { id: "cha2ds2_vasc", name: "CHA2DS2-VASc Score", short_name: "CHA2DS2-VASc", category: "cardiovascular", description: "Stroke risk in atrial fibrillation" },
  { id: "bmi", name: "Body Mass Index (BMI)", short_name: "BMI", category: "general", description: "Calculate body mass index for obesity classification" },
];

const fallbackCategories: CategoryInfo[] = [
  { id: "cardiovascular", name: "Cardiovascular", count: 3 },
  { id: "general", name: "General", count: 1 },
];

// Fetch clinical calculators from API
async function fetchClinicalCalculators(): Promise<CalculatorsResponse> {
  const response = await fetch("/api/calculators/clinical");
  if (!response.ok) {
    throw new Error("Failed to fetch clinical calculators");
  }
  return response.json();
}

// Fetch data-driven calculators from API
async function fetchDataDrivenCalculators(): Promise<DataDrivenCalculatorsResponse> {
  const response = await fetch("/api/calculators/definitions");
  if (!response.ok) {
    throw new Error("Failed to fetch data-driven calculators");
  }
  return response.json();
}

// Merge and deduplicate calculators, preferring data-driven versions
function mergeCalculators(
  clinical: CalculatorSummary[],
  dataDriven: CalculatorSummary[]
): CalculatorSummary[] {
  const calcMap = new Map<string, CalculatorSummary>();

  // Add clinical calculators first
  for (const calc of clinical) {
    calcMap.set(calc.id, calc);
  }

  // Override with data-driven versions (they have more detailed definitions)
  for (const calc of dataDriven) {
    calcMap.set(calc.id, calc);
  }

  return Array.from(calcMap.values());
}

// Rebuild category counts from merged calculators
function buildCategories(calculators: CalculatorSummary[]): CategoryInfo[] {
  const categoryMap = new Map<string, number>();

  for (const calc of calculators) {
    const count = categoryMap.get(calc.category) || 0;
    categoryMap.set(calc.category, count + 1);
  }

  return Array.from(categoryMap.entries())
    .map(([id, count]) => ({
      id,
      name: id.charAt(0).toUpperCase() + id.slice(1).replace(/_/g, " "),
      count,
    }))
    .sort((a, b) => b.count - a.count);
}

const categoryIcons: Record<string, React.ReactNode> = {
  cardiovascular: <Heart className="h-5 w-5" />,
  renal: <Droplets className="h-5 w-5" />,
  hepatic: <Activity className="h-5 w-5" />,
  critical_care: <Gauge className="h-5 w-5" />,
  general: <Scale className="h-5 w-5" />,
  laboratory: <FlaskConical className="h-5 w-5" />,
  pulmonary: <Activity className="h-5 w-5" />,
  neurological: <Brain className="h-5 w-5" />,
  infectious: <Stethoscope className="h-5 w-5" />,
  emergency: <TrendingUp className="h-5 w-5" />,
  surgical: <Activity className="h-5 w-5" />,
  obstetric: <Heart className="h-5 w-5" />,
  metabolic: <FlaskConical className="h-5 w-5" />,
  hematology: <Droplets className="h-5 w-5" />,
  oncology: <Activity className="h-5 w-5" />,
  pediatric: <Heart className="h-5 w-5" />,
  geriatric: <Activity className="h-5 w-5" />,
};

const categoryColors: Record<string, string> = {
  cardiovascular: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  renal: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  hepatic: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  critical_care: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  general: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  laboratory: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
  pulmonary: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
  neurological: "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400",
  infectious: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  emergency: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
  surgical: "bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400",
  obstetric: "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/30 dark:text-fuchsia-400",
  metabolic: "bg-lime-100 text-lime-700 dark:bg-lime-900/30 dark:text-lime-400",
  hematology: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400",
  oncology: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  pediatric: "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400",
  geriatric: "bg-stone-100 text-stone-700 dark:bg-stone-900/30 dark:text-stone-400",
};

export default function CalculatorsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Set<string>>(new Set(["egfr_ckdepi", "cha2ds2_vasc", "bmi"]));
  const [isLoading, setIsLoading] = useState(true);
  const [calculators, setCalculators] = useState<CalculatorSummary[]>(fallbackCalculators);
  const [categories, setCategories] = useState<CategoryInfo[]>(fallbackCategories);
  const [error, setError] = useState<string | null>(null);

  // Fetch calculators from both APIs on mount
  useEffect(() => {
    const loadCalculators = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Fetch from both APIs in parallel
        const [clinicalResult, dataDrivenResult] = await Promise.allSettled([
          fetchClinicalCalculators(),
          fetchDataDrivenCalculators(),
        ]);

        let clinicalCalcs: CalculatorSummary[] = [];
        let dataDrivenCalcs: CalculatorSummary[] = [];

        if (clinicalResult.status === "fulfilled") {
          clinicalCalcs = clinicalResult.value.calculators;
        }

        if (dataDrivenResult.status === "fulfilled") {
          dataDrivenCalcs = dataDrivenResult.value.calculators;
        }

        // Merge calculators, preferring data-driven versions
        const mergedCalculators = mergeCalculators(clinicalCalcs, dataDrivenCalcs);

        if (mergedCalculators.length > 0) {
          setCalculators(mergedCalculators);
          setCategories(buildCategories(mergedCalculators));
        } else {
          // Both APIs failed, use fallback
          setError("Failed to load calculators. Using cached data.");
        }
      } catch (err) {
        console.error("Failed to fetch calculators:", err);
        setError("Failed to load calculators. Using cached data.");
        // Keep fallback data
      } finally {
        setIsLoading(false);
      }
    };
    loadCalculators();
  }, []);

  const filteredCalculators = useMemo(() => {
    return calculators.filter((calc) => {
      const matchesSearch =
        searchQuery === "" ||
        calc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        calc.short_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        calc.description.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory =
        selectedCategory === null || calc.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [calculators, searchQuery, selectedCategory]);

  const favoriteCalculators = useMemo(() => {
    return calculators.filter((calc) => favorites.has(calc.id));
  }, [calculators, favorites]);

  const groupedCalculators = useMemo(() => {
    const groups: Record<string, CalculatorSummary[]> = {};
    for (const calc of filteredCalculators) {
      if (!groups[calc.category]) {
        groups[calc.category] = [];
      }
      groups[calc.category].push(calc);
    }
    return groups;
  }, [filteredCalculators]);

  const toggleFavorite = (calcId: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(calcId)) {
        next.delete(calcId);
      } else {
        next.add(calcId);
      }
      return next;
    });
  };

  const refreshData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch from both APIs in parallel
      const [clinicalResult, dataDrivenResult] = await Promise.allSettled([
        fetchClinicalCalculators(),
        fetchDataDrivenCalculators(),
      ]);

      let clinicalCalcs: CalculatorSummary[] = [];
      let dataDrivenCalcs: CalculatorSummary[] = [];

      if (clinicalResult.status === "fulfilled") {
        clinicalCalcs = clinicalResult.value.calculators;
      }

      if (dataDrivenResult.status === "fulfilled") {
        dataDrivenCalcs = dataDrivenResult.value.calculators;
      }

      // Merge calculators
      const mergedCalculators = mergeCalculators(clinicalCalcs, dataDrivenCalcs);

      if (mergedCalculators.length > 0) {
        setCalculators(mergedCalculators);
        setCategories(buildCategories(mergedCalculators));
      } else {
        setError("Failed to refresh calculators.");
      }
    } catch (err) {
      console.error("Failed to refresh calculators:", err);
      setError("Failed to refresh calculators.");
    } finally {
      setIsLoading(false);
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
            <h1 className="text-2xl font-bold tracking-tight">
              Clinical Calculators
            </h1>
            <p className="text-muted-foreground">
              Validated risk calculators for clinical decision support
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refreshData}
          disabled={isLoading}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Search and Filter */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search calculators..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge
                variant={selectedCategory === null ? "default" : "outline"}
                className="cursor-pointer"
                onClick={() => setSelectedCategory(null)}
              >
                All ({calculators.length})
              </Badge>
              {categories.map((cat) => (
                <Badge
                  key={cat.id}
                  variant={selectedCategory === cat.id ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => setSelectedCategory(cat.id)}
                >
                  {cat.name} ({cat.count})
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950">
          <CardContent className="py-3">
            <p className="text-amber-700 dark:text-amber-300 text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {isLoading && calculators.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center space-y-4">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
              <p className="text-muted-foreground">Loading calculators...</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Favorites Section */}
      {favoriteCalculators.length > 0 && !searchQuery && !selectedCategory && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
              Favorites
            </CardTitle>
            <CardDescription>
              Your frequently used calculators
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {favoriteCalculators.map((calc) => (
                <Link key={calc.id} href={`/clinical/calculators/${calc.id}`}>
                  <Card className="h-full transition-all hover:shadow-md hover:border-primary/50 cursor-pointer">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-3">
                          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${categoryColors[calc.category]}`}>
                            {categoryIcons[calc.category] || <Calculator className="h-5 w-5" />}
                          </div>
                          <div>
                            <h3 className="font-medium text-sm">
                              {calc.short_name}
                            </h3>
                            <p className="text-xs text-muted-foreground capitalize">
                              {calc.category.replace("_", " ")}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 shrink-0"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            toggleFavorite(calc.id);
                          }}
                        >
                          <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Calculator Grid by Category */}
      <div className="space-y-6">
        {Object.entries(groupedCalculators).map(([category, calcs]) => (
          <Card key={category}>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg capitalize">
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${categoryColors[category]}`}>
                  {categoryIcons[category] || <Calculator className="h-4 w-4" />}
                </div>
                {category.replace("_", " ")}
              </CardTitle>
              <CardDescription>
                {calcs.length} calculator{calcs.length !== 1 ? "s" : ""}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {calcs.map((calc) => (
                  <Link key={calc.id} href={`/clinical/calculators/${calc.id}`}>
                    <Card className="h-full transition-all hover:shadow-md hover:border-primary/50 cursor-pointer group">
                      <CardContent className="p-4">
                        <div className="space-y-3">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-3">
                              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${categoryColors[calc.category]}`}>
                                {categoryIcons[calc.category] || <Calculator className="h-5 w-5" />}
                              </div>
                              <div>
                                <h3 className="font-semibold text-sm group-hover:text-primary transition-colors">
                                  {calc.short_name}
                                </h3>
                                <p className="text-xs text-muted-foreground">
                                  {calc.name}
                                </p>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                toggleFavorite(calc.id);
                              }}
                            >
                              {favorites.has(calc.id) ? (
                                <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                              ) : (
                                <StarOff className="h-4 w-4 text-muted-foreground" />
                              )}
                            </Button>
                          </div>
                          <p className="text-xs text-muted-foreground line-clamp-2">
                            {calc.description}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Empty State */}
      {filteredCalculators.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                  <Calculator className="h-8 w-8 text-muted-foreground" />
                </div>
              </div>
              <div>
                <h3 className="text-lg font-medium">No calculators found</h3>
                <p className="text-muted-foreground">
                  Try adjusting your search or filter criteria
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setSearchQuery("");
                  setSelectedCategory(null);
                }}
              >
                Clear filters
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
