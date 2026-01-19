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

// Mock data for client-side rendering (API calls would be used in production)
const mockCalculators: CalculatorSummary[] = [
  // Cardiovascular
  { id: "ascvd", name: "ASCVD 10-Year Risk", short_name: "ASCVD", category: "cardiovascular", description: "10-year atherosclerotic cardiovascular disease risk using Pooled Cohort Equations" },
  { id: "heart", name: "HEART Score", short_name: "HEART", category: "cardiovascular", description: "Major adverse cardiac event risk for chest pain patients" },
  { id: "cha2ds2_vasc", name: "CHA2DS2-VASc Score", short_name: "CHA2DS2-VASc", category: "cardiovascular", description: "Stroke risk in atrial fibrillation" },
  { id: "has_bled", name: "HAS-BLED Score", short_name: "HAS-BLED", category: "cardiovascular", description: "Bleeding risk on anticoagulation" },
  { id: "framingham", name: "Framingham Risk Score", short_name: "Framingham", category: "cardiovascular", description: "10-year cardiovascular disease risk" },
  // Renal
  { id: "egfr_ckdepi", name: "CKD-EPI eGFR (2021)", short_name: "eGFR", category: "renal", description: "Estimated glomerular filtration rate using race-free CKD-EPI 2021 equation" },
  { id: "cockcroft_gault", name: "Creatinine Clearance (Cockcroft-Gault)", short_name: "CrCl", category: "renal", description: "Creatinine clearance for medication dosing" },
  { id: "uacr", name: "UACR Interpretation", short_name: "UACR", category: "renal", description: "Urine albumin-to-creatinine ratio interpretation" },
  // Hepatic
  { id: "meld", name: "MELD/MELD-Na Score", short_name: "MELD", category: "hepatic", description: "Liver disease severity for transplant prioritization" },
  { id: "child_pugh", name: "Child-Pugh Score", short_name: "Child-Pugh", category: "hepatic", description: "Cirrhosis severity classification" },
  { id: "fib4", name: "FIB-4 Score", short_name: "FIB-4", category: "hepatic", description: "Liver fibrosis risk assessment" },
  // Critical Care
  { id: "sofa", name: "SOFA Score", short_name: "SOFA", category: "critical_care", description: "Sequential organ failure assessment" },
  { id: "qsofa", name: "qSOFA Score", short_name: "qSOFA", category: "critical_care", description: "Quick sepsis screening" },
  { id: "wells_pe", name: "Wells Score for PE", short_name: "Wells PE", category: "critical_care", description: "Pulmonary embolism probability" },
  { id: "wells_dvt", name: "Wells Score for DVT", short_name: "Wells DVT", category: "critical_care", description: "Deep vein thrombosis probability" },
  // General
  { id: "bmi", name: "Body Mass Index (BMI)", short_name: "BMI", category: "general", description: "Calculate body mass index for obesity classification" },
  { id: "bsa", name: "Body Surface Area (BSA)", short_name: "BSA", category: "general", description: "Calculate body surface area using Du Bois formula" },
  // Laboratory
  { id: "corrected_calcium", name: "Corrected Calcium", short_name: "Corr Ca", category: "laboratory", description: "Albumin-corrected calcium level" },
  { id: "anion_gap", name: "Anion Gap", short_name: "AG", category: "laboratory", description: "Serum anion gap calculation" },
];

const mockCategories: CategoryInfo[] = [
  { id: "cardiovascular", name: "Cardiovascular", count: 5 },
  { id: "renal", name: "Renal", count: 3 },
  { id: "hepatic", name: "Hepatic", count: 3 },
  { id: "critical_care", name: "Critical Care", count: 4 },
  { id: "general", name: "General", count: 2 },
  { id: "laboratory", name: "Laboratory", count: 2 },
];

const categoryIcons: Record<string, React.ReactNode> = {
  cardiovascular: <Heart className="h-5 w-5" />,
  renal: <Droplets className="h-5 w-5" />,
  hepatic: <Activity className="h-5 w-5" />,
  critical_care: <Gauge className="h-5 w-5" />,
  general: <Scale className="h-5 w-5" />,
  laboratory: <FlaskConical className="h-5 w-5" />,
};

const categoryColors: Record<string, string> = {
  cardiovascular: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  renal: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  hepatic: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  critical_care: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  general: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  laboratory: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
};

export default function CalculatorsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Set<string>>(new Set(["egfr_ckdepi", "cha2ds2_vasc", "bmi"]));
  const [isLoading, setIsLoading] = useState(false);

  const filteredCalculators = useMemo(() => {
    return mockCalculators.filter((calc) => {
      const matchesSearch =
        searchQuery === "" ||
        calc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        calc.short_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        calc.description.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory =
        selectedCategory === null || calc.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [searchQuery, selectedCategory]);

  const favoriteCalculators = useMemo(() => {
    return mockCalculators.filter((calc) => favorites.has(calc.id));
  }, [favorites]);

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
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 500));
    setIsLoading(false);
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
                All ({mockCalculators.length})
              </Badge>
              {mockCategories.map((cat) => (
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
