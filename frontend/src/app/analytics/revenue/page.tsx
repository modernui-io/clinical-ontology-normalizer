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
import {
  ArrowLeft,
  DollarSign,
  TrendingUp,
  Target,
  AlertTriangle,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

interface RevenueOpportunity {
  id: string;
  category: string;
  description: string;
  annual_impact: number;
  confidence: "high" | "medium" | "low";
  source: string;
  action_required: string;
}

interface RevenueSummary {
  total_annual_opportunity: number;
  captured_revenue: number;
  gap_revenue: number;
  high_confidence_total: number;
  medium_confidence_total: number;
  low_confidence_total: number;
  month_over_month_change: number;
}

const mockSummary: RevenueSummary = {
  total_annual_opportunity: 892450,
  captured_revenue: 4215800,
  gap_revenue: 892450,
  high_confidence_total: 534200,
  medium_confidence_total: 245680,
  low_confidence_total: 112570,
  month_over_month_change: 12.4,
};

const mockOpportunities: RevenueOpportunity[] = [
  {
    id: "1", category: "HCC Gap", description: "Heart Failure (HCC85) - undocumented in 23 patients",
    annual_impact: 142560, confidence: "high", source: "HCC Analysis",
    action_required: "Review patients with CHF evidence lacking I50.x codes",
  },
  {
    id: "2", category: "HCC Gap", description: "Diabetes with Complications (HCC37) - specificity gaps in 45 patients",
    annual_impact: 185400, confidence: "high", source: "HCC Analysis",
    action_required: "Update E11.9 to complication-specific codes (E11.21, E11.65, etc.)",
  },
  {
    id: "3", category: "E/M Upcoding", description: "Level 3 visits qualifying for Level 4 based on complexity",
    annual_impact: 98200, confidence: "medium", source: "CPT Analysis",
    action_required: "Review 99213 visits with 3+ chronic conditions or moderate MDM",
  },
  {
    id: "4", category: "HCC Gap", description: "COPD (HCC111) - not recaptured in current year for 18 patients",
    annual_impact: 108240, confidence: "high", source: "HCC Analysis",
    action_required: "Recapture J44.x codes during annual wellness visits",
  },
  {
    id: "5", category: "CDI Query", description: "CKD staging incomplete - missing stage in 34 patients",
    annual_impact: 78500, confidence: "medium", source: "Documentation Review",
    action_required: "Query providers to specify CKD stage (N18.1-N18.5)",
  },
  {
    id: "6", category: "Bundling", description: "Missed separate billing for bundled procedures",
    annual_impact: 67300, confidence: "medium", source: "CPT Bundling",
    action_required: "Review procedures with modifier 59 eligibility",
  },
  {
    id: "7", category: "HCC Gap", description: "Major Depression (HCC155) - severity not specified in 28 patients",
    annual_impact: 89400, confidence: "low", source: "HCC Analysis",
    action_required: "PHQ-9 documentation to support moderate/severe classification",
  },
  {
    id: "8", category: "RAF Optimization", description: "Morbid Obesity (HCC22) - BMI >40 not coded in 15 patients",
    annual_impact: 62850, confidence: "high", source: "Clinical Data",
    action_required: "Add E66.01 for patients with documented BMI >= 40",
  },
  {
    id: "9", category: "CDI Query", description: "Malnutrition documentation gaps in acute care",
    annual_impact: 45000, confidence: "low", source: "Documentation Review",
    action_required: "Implement malnutrition screening and coding protocol",
  },
  {
    id: "10", category: "E/M Upcoding", description: "Prolonged services not billed for visits >54 min",
    annual_impact: 15000, confidence: "medium", source: "Time Documentation",
    action_required: "Apply 99417 for visits exceeding time thresholds",
  },
];

const categoryBreakdown = [
  { category: "HCC Gaps", amount: 588450, pct: 65.9, color: "bg-blue-500" },
  { category: "E/M Optimization", amount: 113200, pct: 12.7, color: "bg-green-500" },
  { category: "CDI Queries", amount: 123500, pct: 13.8, color: "bg-amber-500" },
  { category: "Bundling/Procedures", amount: 67300, pct: 7.5, color: "bg-purple-500" },
];

export default function RevenueImpactPage() {
  const [filter, setFilter] = useState<string>("all");

  const filteredOpportunities = filter === "all"
    ? mockOpportunities
    : mockOpportunities.filter((o) => o.confidence === filter);

  const confidenceColor = {
    high: "bg-green-600 text-white",
    medium: "bg-amber-600 text-white",
    low: "bg-gray-500 text-white",
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
          <h1 className="text-2xl font-bold">Revenue Impact Dashboard</h1>
          <p className="text-muted-foreground">
            HCC gap recovery, coding optimization, and revenue opportunities
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Opportunity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              ${mockSummary.total_annual_opportunity.toLocaleString()}
            </div>
            <div className="flex items-center text-xs text-green-600 mt-1">
              <ArrowUpRight className="h-3 w-3 mr-0.5" />
              {mockSummary.month_over_month_change}% vs last month
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              High Confidence
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${mockSummary.high_confidence_total.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {Math.round((mockSummary.high_confidence_total / mockSummary.total_annual_opportunity) * 100)}% of total
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Captured Revenue
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${mockSummary.captured_revenue.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Annual captured RAF</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Gap Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {Math.round((mockSummary.gap_revenue / (mockSummary.captured_revenue + mockSummary.gap_revenue)) * 100)}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">Uncaptured vs total</p>
          </CardContent>
        </Card>
      </div>

      {/* Category Breakdown */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <BarChart3 className="h-5 w-5" /> Revenue by Category
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {categoryBreakdown.map((cat) => (
              <div key={cat.category} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{cat.category}</span>
                  <span className="text-muted-foreground">
                    ${cat.amount.toLocaleString()} ({cat.pct}%)
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full ${cat.color} rounded-full`}
                    style={{ width: `${cat.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Opportunities List */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Opportunities</CardTitle>
            <div className="flex gap-1">
              {["all", "high", "medium", "low"].map((f) => (
                <Button
                  key={f}
                  variant={filter === f ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilter(f)}
                  className="text-xs"
                >
                  {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {filteredOpportunities.map((opp) => (
              <div key={opp.id} className="p-3 border rounded-lg">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className="text-xs">
                        {opp.category}
                      </Badge>
                      <Badge className={`text-xs ${confidenceColor[opp.confidence]}`}>
                        {opp.confidence}
                      </Badge>
                    </div>
                    <p className="text-sm font-medium">{opp.description}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {opp.action_required}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-green-600">
                      ${opp.annual_impact.toLocaleString()}
                    </p>
                    <p className="text-xs text-muted-foreground">/year</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
