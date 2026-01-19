"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Target,
  Activity,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  Download,
  ChevronDown,
  ChevronUp,
  Search,
  Star,
  Users,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  ArrowLeft,
  Filter,
  ExternalLink,
  FileText,
  Stethoscope,
  Heart,
  Brain,
  Baby,
  ShieldAlert,
  Pill,
  Wind,
  PersonStanding,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface MeasureMetadata {
  nqf_id: string | null;
  cms_id: string | null;
  steward: string;
  domain: string;
  description: string;
  rationale: string;
  specifications_url: string | null;
}

interface BenchmarkInfo {
  percentile_50th: number;
  percentile_90th: number;
  national_average: number | null;
  star_rating: number;
  meets_benchmark: boolean;
}

interface PerformanceRate {
  rate: number;
  rate_display: string;
  numerator: number;
  denominator: number;
  excluded: number;
  eligible_population: number;
}

interface TrendPoint {
  period: string;
  period_start: string;
  period_end: string;
  rate: number;
  numerator: number;
  denominator: number;
}

interface MeasureResponse {
  id: string;
  name: string;
  category: string;
  measure_type: string;
  version: string;
  metadata: MeasureMetadata;
  clinical_guidance: string;
  default_priority: string;
  performance: PerformanceRate | null;
  benchmark: BenchmarkInfo | null;
  trend: TrendPoint[] | null;
  total_gaps: number;
  critical_gaps: number;
  high_priority_gaps: number;
}

interface MeasureListResponse {
  request_id: string;
  total: number;
  measures: MeasureResponse[];
  by_category: Record<string, number>;
  by_type: Record<string, number>;
}

interface PerformanceSummary {
  request_id: string;
  period_start: string;
  period_end: string;
  total_measures: number;
  measures_meeting_benchmark: number;
  average_performance: number;
  total_gaps: number;
  critical_gaps: number;
  gap_closure_rate: number;
  by_category: Record<string, {
    measure_count: number;
    average_rate: number;
    total_gaps: number;
    critical_gaps: number;
  }>;
  star_distribution: Record<string, number>;
}

// ============================================================================
// Mock Data
// ============================================================================

const mockMeasures: MeasureResponse[] = [
  {
    id: "HEDIS-CDC-HBA1C",
    name: "Diabetes: HbA1c Control (<8%)",
    category: "diabetes",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "0059",
      cms_id: "CMS122v10",
      steward: "NCQA",
      domain: "Diabetes",
      description: "Percentage of patients 18-75 with diabetes whose HbA1c was <8%",
      rationale: "Good glycemic control reduces complications",
      specifications_url: "https://www.ncqa.org/hedis/measures/comprehensive-diabetes-care",
    },
    clinical_guidance: "Target HbA1c <8% for most patients. Consider individualized targets.",
    default_priority: "high",
    performance: {
      rate: 0.72,
      rate_display: "72.0%",
      numerator: 900,
      denominator: 1250,
      excluded: 45,
      eligible_population: 1295,
    },
    benchmark: {
      percentile_50th: 0.65,
      percentile_90th: 0.78,
      national_average: 0.68,
      star_rating: 4,
      meets_benchmark: true,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.68, numerator: 850, denominator: 1250 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.69, numerator: 862, denominator: 1249 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.70, numerator: 875, denominator: 1250 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.71, numerator: 887, denominator: 1249 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.72, numerator: 900, denominator: 1250 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.72, numerator: 900, denominator: 1250 },
    ],
    total_gaps: 350,
    critical_gaps: 28,
    high_priority_gaps: 105,
  },
  {
    id: "HEDIS-CDC-EYE",
    name: "Diabetes: Eye Exam",
    category: "diabetes",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "0055",
      cms_id: "CMS131v10",
      steward: "NCQA",
      domain: "Diabetes",
      description: "Percentage of patients with diabetes who had a retinal eye exam",
      rationale: "Early detection of diabetic retinopathy prevents vision loss",
      specifications_url: null,
    },
    clinical_guidance: "Annual dilated eye exam by ophthalmologist or optometrist.",
    default_priority: "high",
    performance: {
      rate: 0.58,
      rate_display: "58.0%",
      numerator: 725,
      denominator: 1250,
      excluded: 30,
      eligible_population: 1280,
    },
    benchmark: {
      percentile_50th: 0.58,
      percentile_90th: 0.72,
      national_average: 0.58,
      star_rating: 3,
      meets_benchmark: true,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.55, numerator: 687, denominator: 1249 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.56, numerator: 700, denominator: 1250 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.57, numerator: 712, denominator: 1249 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.57, numerator: 712, denominator: 1249 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.58, numerator: 725, denominator: 1250 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.58, numerator: 725, denominator: 1250 },
    ],
    total_gaps: 525,
    critical_gaps: 42,
    high_priority_gaps: 157,
  },
  {
    id: "HEDIS-BCS",
    name: "Breast Cancer Screening",
    category: "preventive",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "2372",
      cms_id: "CMS125v10",
      steward: "NCQA",
      domain: "Cancer Screening",
      description: "Women 50-74 who had a mammogram in the past 2 years",
      rationale: "Early detection improves breast cancer outcomes",
      specifications_url: null,
    },
    clinical_guidance: "Screening mammography every 2 years for women 50-74.",
    default_priority: "high",
    performance: {
      rate: 0.75,
      rate_display: "75.0%",
      numerator: 1185,
      denominator: 1580,
      excluded: 62,
      eligible_population: 1642,
    },
    benchmark: {
      percentile_50th: 0.72,
      percentile_90th: 0.82,
      national_average: 0.74,
      star_rating: 4,
      meets_benchmark: true,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.73, numerator: 1153, denominator: 1580 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.74, numerator: 1169, denominator: 1580 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.74, numerator: 1169, denominator: 1580 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.75, numerator: 1185, denominator: 1580 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.75, numerator: 1185, denominator: 1580 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.75, numerator: 1185, denominator: 1580 },
    ],
    total_gaps: 395,
    critical_gaps: 48,
    high_priority_gaps: 118,
  },
  {
    id: "HEDIS-COL",
    name: "Colorectal Cancer Screening",
    category: "preventive",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "0034",
      cms_id: "CMS130v10",
      steward: "NCQA",
      domain: "Cancer Screening",
      description: "Adults 50-75 who had appropriate colorectal cancer screening",
      rationale: "Screening reduces colorectal cancer mortality",
      specifications_url: null,
    },
    clinical_guidance: "Colonoscopy every 10 years, or annual FIT/FOBT, or FIT-DNA every 3 years.",
    default_priority: "high",
    performance: {
      rate: 0.68,
      rate_display: "68.0%",
      numerator: 2176,
      denominator: 3200,
      excluded: 145,
      eligible_population: 3345,
    },
    benchmark: {
      percentile_50th: 0.68,
      percentile_90th: 0.80,
      national_average: 0.68,
      star_rating: 3,
      meets_benchmark: true,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.66, numerator: 2112, denominator: 3200 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.67, numerator: 2144, denominator: 3200 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.67, numerator: 2144, denominator: 3200 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.68, numerator: 2176, denominator: 3200 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.68, numerator: 2176, denominator: 3200 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.68, numerator: 2176, denominator: 3200 },
    ],
    total_gaps: 1024,
    critical_gaps: 85,
    high_priority_gaps: 307,
  },
  {
    id: "HEDIS-CBP",
    name: "Controlling High Blood Pressure",
    category: "cardiovascular",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "0018",
      cms_id: "CMS165v10",
      steward: "NCQA",
      domain: "Cardiovascular",
      description: "Patients with hypertension whose BP was adequately controlled (<140/90)",
      rationale: "BP control reduces cardiovascular events",
      specifications_url: null,
    },
    clinical_guidance: "Target BP <140/90 for most adults. Consider <130/80 for high-risk patients.",
    default_priority: "critical",
    performance: {
      rate: 0.62,
      rate_display: "62.0%",
      numerator: 1302,
      denominator: 2100,
      excluded: 85,
      eligible_population: 2185,
    },
    benchmark: {
      percentile_50th: 0.65,
      percentile_90th: 0.78,
      national_average: 0.64,
      star_rating: 2,
      meets_benchmark: false,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.64, numerator: 1344, denominator: 2100 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.63, numerator: 1323, denominator: 2100 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.63, numerator: 1323, denominator: 2100 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.62, numerator: 1302, denominator: 2100 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.62, numerator: 1302, denominator: 2100 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.62, numerator: 1302, denominator: 2100 },
    ],
    total_gaps: 798,
    critical_gaps: 120,
    high_priority_gaps: 239,
  },
  {
    id: "HEDIS-SPC",
    name: "Statin Therapy for Cardiovascular Disease",
    category: "cardiovascular",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "N/A",
      cms_id: "CMS347v5",
      steward: "NCQA",
      domain: "Cardiovascular",
      description: "Patients with ASCVD who were prescribed statin therapy",
      rationale: "Statins reduce cardiovascular events in ASCVD patients",
      specifications_url: null,
    },
    clinical_guidance: "High-intensity statin for all patients with clinical ASCVD.",
    default_priority: "critical",
    performance: {
      rate: 0.85,
      rate_display: "85.0%",
      numerator: 756,
      denominator: 890,
      excluded: 25,
      eligible_population: 915,
    },
    benchmark: {
      percentile_50th: 0.80,
      percentile_90th: 0.90,
      national_average: 0.82,
      star_rating: 4,
      meets_benchmark: true,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.82, numerator: 729, denominator: 889 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.83, numerator: 738, denominator: 889 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.84, numerator: 747, denominator: 889 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.84, numerator: 747, denominator: 889 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.85, numerator: 756, denominator: 889 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.85, numerator: 756, denominator: 890 },
    ],
    total_gaps: 134,
    critical_gaps: 15,
    high_priority_gaps: 40,
  },
  {
    id: "HEDIS-AMM-ACUTE",
    name: "Antidepressant Medication Management - Acute",
    category: "behavioral_health",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "0105",
      cms_id: "CMS128v10",
      steward: "NCQA",
      domain: "Behavioral Health",
      description: "Patients with depression who remained on antidepressant for 84 days",
      rationale: "Adequate duration of antidepressant therapy improves outcomes",
      specifications_url: null,
    },
    clinical_guidance: "Continue antidepressant for at least 84 days (acute phase treatment).",
    default_priority: "high",
    performance: {
      rate: 0.55,
      rate_display: "55.0%",
      numerator: 248,
      denominator: 450,
      excluded: 18,
      eligible_population: 468,
    },
    benchmark: {
      percentile_50th: 0.58,
      percentile_90th: 0.72,
      national_average: 0.56,
      star_rating: 2,
      meets_benchmark: false,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.52, numerator: 234, denominator: 450 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.53, numerator: 238, denominator: 449 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.54, numerator: 243, denominator: 450 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.54, numerator: 243, denominator: 450 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.55, numerator: 247, denominator: 449 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.55, numerator: 248, denominator: 450 },
    ],
    total_gaps: 202,
    critical_gaps: 35,
    high_priority_gaps: 60,
  },
  {
    id: "CQM-IMM-FLU",
    name: "Adult Immunization: Influenza",
    category: "preventive",
    measure_type: "cqm",
    version: "2024",
    metadata: {
      nqf_id: "0041",
      cms_id: "CMS147v11",
      steward: "CMS",
      domain: "Immunizations",
      description: "Adults 18+ who received influenza vaccine during flu season",
      rationale: "Influenza vaccination reduces flu-related illness and death",
      specifications_url: null,
    },
    clinical_guidance: "Annual influenza vaccination for all adults, especially high-risk groups.",
    default_priority: "medium",
    performance: {
      rate: 0.48,
      rate_display: "48.0%",
      numerator: 2496,
      denominator: 5200,
      excluded: 210,
      eligible_population: 5410,
    },
    benchmark: {
      percentile_50th: 0.48,
      percentile_90th: 0.60,
      national_average: 0.48,
      star_rating: 3,
      meets_benchmark: true,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.45, numerator: 2340, denominator: 5200 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.46, numerator: 2392, denominator: 5200 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.47, numerator: 2444, denominator: 5200 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.47, numerator: 2444, denominator: 5200 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.48, numerator: 2496, denominator: 5200 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.48, numerator: 2496, denominator: 5200 },
    ],
    total_gaps: 2704,
    critical_gaps: 180,
    high_priority_gaps: 811,
  },
  {
    id: "HEDIS-AWC",
    name: "Annual Wellness Visit",
    category: "preventive",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "0039",
      cms_id: null,
      steward: "NCQA",
      domain: "Preventive Care",
      description: "Adults 18+ who had an annual wellness visit during the measurement year",
      rationale: "Annual wellness visits support preventive care and health assessment",
      specifications_url: null,
    },
    clinical_guidance: "Schedule annual wellness visit to assess health status and preventive care needs.",
    default_priority: "medium",
    performance: {
      rate: 0.52,
      rate_display: "52.0%",
      numerator: 2600,
      denominator: 5000,
      excluded: 150,
      eligible_population: 5150,
    },
    benchmark: {
      percentile_50th: 0.52,
      percentile_90th: 0.68,
      national_average: 0.52,
      star_rating: 3,
      meets_benchmark: true,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.50, numerator: 2500, denominator: 5000 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.51, numerator: 2550, denominator: 5000 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.51, numerator: 2550, denominator: 5000 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.52, numerator: 2600, denominator: 5000 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.52, numerator: 2600, denominator: 5000 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.52, numerator: 2600, denominator: 5000 },
    ],
    total_gaps: 2400,
    critical_gaps: 150,
    high_priority_gaps: 720,
  },
  {
    id: "HEDIS-KED",
    name: "Kidney Health Evaluation for Diabetes",
    category: "diabetes",
    measure_type: "hedis",
    version: "2024",
    metadata: {
      nqf_id: "3061",
      cms_id: null,
      steward: "NCQA",
      domain: "Diabetes",
      description: "Patients with diabetes who had kidney health evaluation (eGFR + uACR)",
      rationale: "Early detection of diabetic kidney disease enables intervention",
      specifications_url: null,
    },
    clinical_guidance: "Order both eGFR and urine albumin-to-creatinine ratio annually.",
    default_priority: "high",
    performance: {
      rate: 0.38,
      rate_display: "38.0%",
      numerator: 475,
      denominator: 1250,
      excluded: 30,
      eligible_population: 1280,
    },
    benchmark: {
      percentile_50th: 0.38,
      percentile_90th: 0.55,
      national_average: 0.38,
      star_rating: 3,
      meets_benchmark: true,
    },
    trend: [
      { period: "2024-01", period_start: "2024-01-01", period_end: "2024-01-31", rate: 0.35, numerator: 437, denominator: 1249 },
      { period: "2024-02", period_start: "2024-02-01", period_end: "2024-02-29", rate: 0.36, numerator: 450, denominator: 1250 },
      { period: "2024-03", period_start: "2024-03-01", period_end: "2024-03-31", rate: 0.37, numerator: 462, denominator: 1249 },
      { period: "2024-04", period_start: "2024-04-01", period_end: "2024-04-30", rate: 0.37, numerator: 462, denominator: 1249 },
      { period: "2024-05", period_start: "2024-05-01", period_end: "2024-05-31", rate: 0.38, numerator: 475, denominator: 1250 },
      { period: "2024-06", period_start: "2024-06-01", period_end: "2024-06-30", rate: 0.38, numerator: 475, denominator: 1250 },
    ],
    total_gaps: 775,
    critical_gaps: 62,
    high_priority_gaps: 232,
  },
];

const mockPerformanceSummary: PerformanceSummary = {
  request_id: "mock-001",
  period_start: "2024-01-01",
  period_end: "2024-06-30",
  total_measures: 10,
  measures_meeting_benchmark: 7,
  average_performance: 0.613,
  total_gaps: 9307,
  critical_gaps: 765,
  gap_closure_rate: 0.12,
  by_category: {
    diabetes: { measure_count: 3, average_rate: 0.56, total_gaps: 1650, critical_gaps: 132 },
    cardiovascular: { measure_count: 2, average_rate: 0.735, total_gaps: 932, critical_gaps: 135 },
    preventive: { measure_count: 4, average_rate: 0.608, total_gaps: 6523, critical_gaps: 463 },
    behavioral_health: { measure_count: 1, average_rate: 0.55, total_gaps: 202, critical_gaps: 35 },
  },
  star_distribution: { "1": 0, "2": 2, "3": 4, "4": 4, "5": 0 },
};

// ============================================================================
// Helper Functions
// ============================================================================

const getCategoryIcon = (category: string) => {
  switch (category) {
    case "diabetes":
      return <Activity className="h-4 w-4" />;
    case "cardiovascular":
      return <Heart className="h-4 w-4" />;
    case "preventive":
      return <Target className="h-4 w-4" />;
    case "behavioral_health":
      return <Brain className="h-4 w-4" />;
    case "respiratory":
      return <Wind className="h-4 w-4" />;
    case "musculoskeletal":
      return <PersonStanding className="h-4 w-4" />;
    case "womens_health":
      return <Stethoscope className="h-4 w-4" />;
    case "pediatric":
      return <Baby className="h-4 w-4" />;
    case "safety":
      return <ShieldAlert className="h-4 w-4" />;
    case "medication_adherence":
      return <Pill className="h-4 w-4" />;
    default:
      return <Target className="h-4 w-4" />;
  }
};

const getCategoryLabel = (category: string): string => {
  const labels: Record<string, string> = {
    diabetes: "Diabetes",
    cardiovascular: "Cardiovascular",
    preventive: "Preventive",
    behavioral_health: "Behavioral Health",
    respiratory: "Respiratory",
    musculoskeletal: "Musculoskeletal",
    womens_health: "Women's Health",
    pediatric: "Pediatric",
    safety: "Safety",
    medication_adherence: "Medication Adherence",
  };
  return labels[category] || category;
};

const getPerformanceColor = (rate: number, benchmark50: number, benchmark90: number): string => {
  if (rate >= benchmark90) return "text-green-600 dark:text-green-400";
  if (rate >= benchmark50) return "text-emerald-600 dark:text-emerald-400";
  if (rate >= benchmark50 * 0.9) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
};

const getPerformanceBgColor = (rate: number, benchmark50: number): string => {
  if (rate >= benchmark50 * 1.1) return "bg-green-500";
  if (rate >= benchmark50) return "bg-emerald-500";
  if (rate >= benchmark50 * 0.9) return "bg-amber-500";
  return "bg-red-500";
};

const getMeasureTypeColor = (type: string): string => {
  switch (type) {
    case "hedis":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "cqm":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    case "mips":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getStarDisplay = (rating: number) => {
  return Array.from({ length: 5 }, (_, i) => (
    <Star
      key={i}
      className={`h-4 w-4 ${
        i < rating
          ? "fill-amber-400 text-amber-400"
          : "fill-gray-200 text-gray-200 dark:fill-gray-700 dark:text-gray-700"
      }`}
    />
  ));
};

const getTrendDirection = (trend: TrendPoint[] | null): "up" | "down" | "stable" => {
  if (!trend || trend.length < 2) return "stable";
  const first = trend[0].rate;
  const last = trend[trend.length - 1].rate;
  if (last > first + 0.02) return "up";
  if (last < first - 0.02) return "down";
  return "stable";
};

// ============================================================================
// Sparkline Component
// ============================================================================

function TrendSparkline({ data, height = 32 }: { data: TrendPoint[]; height?: number }) {
  if (data.length < 2) return null;

  const rates = data.map(d => d.rate);
  const min = Math.min(...rates);
  const max = Math.max(...rates);
  const range = max - min || 0.1;
  const width = 80;
  const stepX = width / (rates.length - 1);

  const points = rates
    .map((v, i) => `${i * stepX},${height - 2 - ((v - min) / range) * (height - 4)}`)
    .join(" ");

  const direction = getTrendDirection(data);
  const color = direction === "up" ? "text-green-500" : direction === "down" ? "text-red-500" : "text-gray-400";

  return (
    <svg width={width} height={height} className={color}>
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function QualityMeasuresDashboard() {
  const [measures, setMeasures] = useState<MeasureResponse[]>(mockMeasures);
  const [performanceSummary, setPerformanceSummary] = useState<PerformanceSummary>(mockPerformanceSummary);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [measureTypeFilter, setMeasureTypeFilter] = useState<string>("all");
  const [timePeriod, setTimePeriod] = useState<string>("current_year");
  const [expandedMeasure, setExpandedMeasure] = useState<string | null>(null);

  // Unique categories and types
  const categories = ["all", ...new Set(measures.map(m => m.category))];
  const measureTypes = ["all", ...new Set(measures.map(m => m.measure_type))];

  // Filter measures
  const filteredMeasures = measures.filter(m => {
    const matchesSearch = searchQuery === "" ||
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.metadata.domain.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = categoryFilter === "all" || m.category === categoryFilter;
    const matchesType = measureTypeFilter === "all" || m.measure_type === measureTypeFilter;
    return matchesSearch && matchesCategory && matchesType;
  });

  // Calculate summary stats
  const totalGaps = filteredMeasures.reduce((sum, m) => sum + m.total_gaps, 0);
  const criticalGaps = filteredMeasures.reduce((sum, m) => sum + m.critical_gaps, 0);
  const meetsBenchmark = filteredMeasures.filter(m => m.benchmark?.meets_benchmark).length;
  const avgPerformance = filteredMeasures.length > 0
    ? filteredMeasures.reduce((sum, m) => sum + (m.performance?.rate || 0), 0) / filteredMeasures.length
    : 0;

  const handleExport = () => {
    const exportData = {
      exported_at: new Date().toISOString(),
      period: timePeriod,
      summary: {
        total_measures: filteredMeasures.length,
        average_performance: avgPerformance,
        total_gaps: totalGaps,
        critical_gaps: criticalGaps,
      },
      measures: filteredMeasures,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quality-measures-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/quality">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Quality Measures Dashboard</h1>
            <p className="text-muted-foreground">
              Performance scorecard for HEDIS, CQM, and eCQM measures
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Link href="/quality/gaps">
            <Button size="sm">
              <AlertCircle className="mr-2 h-4 w-4" />
              View Gaps ({totalGaps.toLocaleString()})
            </Button>
          </Link>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Average Performance</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(avgPerformance * 100).toFixed(1)}%</div>
            <Progress value={avgPerformance * 100} className="mt-2 h-2" />
            <p className="text-xs text-muted-foreground mt-2">
              {meetsBenchmark}/{filteredMeasures.length} measures meet benchmark
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Care Gaps</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalGaps.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-red-600 dark:text-red-400 font-medium">
                {criticalGaps} critical
              </span>{" "}
              gaps require attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Measures Tracked</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{filteredMeasures.length}</div>
            <p className="text-xs text-muted-foreground">
              {filteredMeasures.filter(m => m.measure_type === "hedis").length} HEDIS,{" "}
              {filteredMeasures.filter(m => m.measure_type === "cqm").length} CQM
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Star Rating</CardTitle>
            <Star className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-1">
              {getStarDisplay(
                Math.round(
                  filteredMeasures.reduce((sum, m) => sum + (m.benchmark?.star_rating || 0), 0) /
                    filteredMeasures.length || 0
                )
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Average across all measures
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Category Performance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Performance by Category
          </CardTitle>
          <CardDescription>Aggregate performance across measure categories</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {Object.entries(performanceSummary.by_category).map(([cat, data]) => (
              <div key={cat} className="rounded-lg border p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getCategoryIcon(cat)}
                    <span className="font-medium">{getCategoryLabel(cat)}</span>
                  </div>
                  <Badge variant="outline">{data.measure_count}</Badge>
                </div>
                <div className="text-2xl font-bold">{(data.average_rate * 100).toFixed(1)}%</div>
                <Progress value={data.average_rate * 100} className="h-2" />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{data.total_gaps.toLocaleString()} gaps</span>
                  <span className="text-red-600">{data.critical_gaps} critical</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search measures..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
          />
        </div>

        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-40">
            <Filter className="mr-2 h-4 w-4" />
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            {categories.map((cat) => (
              <SelectItem key={cat} value={cat}>
                {cat === "all" ? "All Categories" : getCategoryLabel(cat)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={measureTypeFilter} onValueChange={setMeasureTypeFilter}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="hedis">HEDIS</SelectItem>
            <SelectItem value="cqm">CQM</SelectItem>
            <SelectItem value="mips">MIPS</SelectItem>
          </SelectContent>
        </Select>

        <Select value={timePeriod} onValueChange={setTimePeriod}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Time Period" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="current_year">Current Year</SelectItem>
            <SelectItem value="last_12_months">Last 12 Months</SelectItem>
            <SelectItem value="last_6_months">Last 6 Months</SelectItem>
            <SelectItem value="last_year">Last Year</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Measures Table */}
      <Card>
        <CardHeader>
          <CardTitle>Quality Measure Performance</CardTitle>
          <CardDescription>Click on a measure to see detailed information</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {filteredMeasures.map((measure) => (
              <div key={measure.id} className="rounded-lg border transition-colors">
                {/* Measure Row */}
                <div
                  className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/50"
                  onClick={() =>
                    setExpandedMeasure(expandedMeasure === measure.id ? null : measure.id)
                  }
                >
                  <div className="flex-1 space-y-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium truncate">{measure.name}</span>
                      <Badge className={getMeasureTypeColor(measure.measure_type)}>
                        {measure.measure_type.toUpperCase()}
                      </Badge>
                      <Badge variant="outline" className="gap-1">
                        {getCategoryIcon(measure.category)}
                        {getCategoryLabel(measure.category)}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{measure.id}</code>
                      {measure.metadata.nqf_id && (
                        <span className="text-xs">NQF: {measure.metadata.nqf_id}</span>
                      )}
                      <span className="flex items-center gap-1">{getStarDisplay(measure.benchmark?.star_rating || 0)}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Performance Rate */}
                    <div className="text-right">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-lg font-bold ${
                            measure.performance && measure.benchmark
                              ? getPerformanceColor(
                                  measure.performance.rate,
                                  measure.benchmark.percentile_50th,
                                  measure.benchmark.percentile_90th
                                )
                              : ""
                          }`}
                        >
                          {measure.performance?.rate_display || "N/A"}
                        </span>
                        {getTrendDirection(measure.trend) === "up" ? (
                          <ArrowUpRight className="h-4 w-4 text-green-600" />
                        ) : getTrendDirection(measure.trend) === "down" ? (
                          <ArrowDownRight className="h-4 w-4 text-red-600" />
                        ) : (
                          <Minus className="h-4 w-4 text-gray-400" />
                        )}
                      </div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <span>Benchmark: {((measure.benchmark?.percentile_50th || 0) * 100).toFixed(0)}%</span>
                        {measure.benchmark?.meets_benchmark ? (
                          <CheckCircle className="h-3 w-3 text-green-600" />
                        ) : (
                          <AlertCircle className="h-3 w-3 text-amber-500" />
                        )}
                      </div>
                    </div>

                    {/* Sparkline */}
                    {measure.trend && <TrendSparkline data={measure.trend} />}

                    {/* Progress Bar */}
                    <div className="w-24 hidden lg:block">
                      <Progress
                        value={(measure.performance?.rate || 0) * 100}
                        className="h-2"
                      />
                    </div>

                    {/* Gaps */}
                    <div className="text-right min-w-[80px]">
                      <div className="text-sm font-medium">{measure.total_gaps.toLocaleString()} gaps</div>
                      {measure.critical_gaps > 0 && (
                        <div className="text-xs text-red-600">{measure.critical_gaps} critical</div>
                      )}
                    </div>

                    {/* Expand Icon */}
                    {expandedMeasure === measure.id ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </div>
                </div>

                {/* Expanded Details */}
                {expandedMeasure === measure.id && (
                  <div className="border-t p-4 bg-muted/20">
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                      {/* Description */}
                      <div>
                        <h4 className="text-sm font-medium mb-2">Description</h4>
                        <p className="text-sm text-muted-foreground">{measure.metadata.description}</p>
                        <p className="text-xs text-muted-foreground mt-2">
                          <strong>Steward:</strong> {measure.metadata.steward}
                        </p>
                      </div>

                      {/* Population */}
                      <div>
                        <h4 className="text-sm font-medium mb-2">Population</h4>
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Eligible:</span>
                            <span>{measure.performance?.eligible_population.toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Numerator:</span>
                            <span>{measure.performance?.numerator.toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Denominator:</span>
                            <span>{measure.performance?.denominator.toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Excluded:</span>
                            <span>{measure.performance?.excluded.toLocaleString()}</span>
                          </div>
                        </div>
                      </div>

                      {/* Benchmarks */}
                      <div>
                        <h4 className="text-sm font-medium mb-2">Benchmarks</h4>
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">50th percentile:</span>
                            <span>{((measure.benchmark?.percentile_50th || 0) * 100).toFixed(0)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">90th percentile:</span>
                            <span>{((measure.benchmark?.percentile_90th || 0) * 100).toFixed(0)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">National average:</span>
                            <span>{((measure.benchmark?.national_average || 0) * 100).toFixed(0)}%</span>
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div>
                        <h4 className="text-sm font-medium mb-2">Clinical Guidance</h4>
                        <p className="text-sm text-muted-foreground mb-3">{measure.clinical_guidance}</p>
                        <div className="space-y-2">
                          <Link href={`/quality/gaps?measure=${measure.id}`}>
                            <Button variant="outline" size="sm" className="w-full">
                              <Users className="mr-2 h-4 w-4" />
                              View Patient Gaps
                            </Button>
                          </Link>
                          {measure.metadata.specifications_url && (
                            <Button variant="outline" size="sm" className="w-full" asChild>
                              <a
                                href={measure.metadata.specifications_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <ExternalLink className="mr-2 h-4 w-4" />
                                Specifications
                              </a>
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {filteredMeasures.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Target className="h-12 w-12 mb-2 opacity-50" />
                <p>No measures match your filters</p>
                <Button
                  variant="link"
                  onClick={() => {
                    setSearchQuery("");
                    setCategoryFilter("all");
                    setMeasureTypeFilter("all");
                  }}
                >
                  Clear filters
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
