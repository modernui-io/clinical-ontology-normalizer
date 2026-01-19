"use client";

import { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Download,
  Search,
  Filter,
  ArrowLeft,
  User,
  Phone,
  Mail,
  Calendar,
  Activity,
  Target,
  Heart,
  Brain,
  Baby,
  ShieldAlert,
  Pill,
  Wind,
  PersonStanding,
  Stethoscope,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Send,
  MessageSquare,
  FileText,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface PatientGap {
  id: string;
  patient_id: string;
  patient_name: string | null;
  measure_id: string;
  measure_name: string;
  category: string;
  missing_element: string;
  missing_codes: string[];
  due_date: string;
  priority: string;
  days_overdue: number;
  last_performed: string | null;
  recommendation: string;
  patient_instructions: string;
  attributed_provider_id: string | null;
  attributed_provider_name: string | null;
  status: string;
  scheduled_date: string | null;
  closed_date: string | null;
  closed_by: string | null;
}

interface GapListResponse {
  request_id: string;
  total: number;
  total_critical: number;
  total_high: number;
  total_medium: number;
  total_low: number;
  gaps: PatientGap[];
}

// ============================================================================
// Mock Data
// ============================================================================

const mockGaps: PatientGap[] = [
  {
    id: "gap-001",
    patient_id: "P001",
    patient_name: "John Smith",
    measure_id: "HEDIS-CDC-HBA1C",
    measure_name: "Diabetes: HbA1c Control (<8%)",
    category: "diabetes",
    missing_element: "HbA1c test overdue by 45 days",
    missing_codes: ["83036"],
    due_date: "2024-11-15",
    priority: "critical",
    days_overdue: 45,
    last_performed: "2024-05-15",
    recommendation: "Order HbA1c test. Target <8% for most patients.",
    patient_instructions: "Please schedule a blood test to check your diabetes control.",
    attributed_provider_id: "DR001",
    attributed_provider_name: "Dr. Sarah Johnson",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-002",
    patient_id: "P002",
    patient_name: "Mary Johnson",
    measure_id: "HEDIS-CDC-EYE",
    measure_name: "Diabetes: Eye Exam",
    category: "diabetes",
    missing_element: "Annual dilated eye exam not documented",
    missing_codes: ["92012", "92014"],
    due_date: "2024-12-31",
    priority: "high",
    days_overdue: 0,
    last_performed: "2023-08-20",
    recommendation: "Schedule dilated eye exam with ophthalmologist.",
    patient_instructions: "You are due for an annual eye exam to check for diabetic eye disease.",
    attributed_provider_id: "DR001",
    attributed_provider_name: "Dr. Sarah Johnson",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-003",
    patient_id: "P003",
    patient_name: "Robert Williams",
    measure_id: "HEDIS-CBP",
    measure_name: "Controlling High Blood Pressure",
    category: "cardiovascular",
    missing_element: "Last BP reading 148/94 (target: <140/90)",
    missing_codes: [],
    due_date: "2024-12-31",
    priority: "critical",
    days_overdue: 0,
    last_performed: "2024-12-01",
    recommendation: "Medication adjustment recommended. Schedule follow-up.",
    patient_instructions: "Your blood pressure needs attention. Please schedule a follow-up visit.",
    attributed_provider_id: "DR002",
    attributed_provider_name: "Dr. Michael Chen",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-004",
    patient_id: "P004",
    patient_name: "Lisa Brown",
    measure_id: "HEDIS-BCS",
    measure_name: "Breast Cancer Screening",
    category: "preventive",
    missing_element: "Mammogram due (last: 2023-06-15)",
    missing_codes: ["77067", "77066"],
    due_date: "2025-06-15",
    priority: "medium",
    days_overdue: 0,
    last_performed: "2023-06-15",
    recommendation: "Schedule screening mammogram.",
    patient_instructions: "You are due for your routine breast cancer screening mammogram.",
    attributed_provider_id: "DR002",
    attributed_provider_name: "Dr. Michael Chen",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-005",
    patient_id: "P005",
    patient_name: "David Garcia",
    measure_id: "HEDIS-COL",
    measure_name: "Colorectal Cancer Screening",
    category: "preventive",
    missing_element: "No colonoscopy or FIT in record",
    missing_codes: ["45378", "82274"],
    due_date: "2024-12-31",
    priority: "high",
    days_overdue: 0,
    last_performed: null,
    recommendation: "Discuss screening options: colonoscopy or annual FIT.",
    patient_instructions: "You are overdue for colorectal cancer screening. Please schedule an appointment.",
    attributed_provider_id: "DR003",
    attributed_provider_name: "Dr. Emily Rodriguez",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-006",
    patient_id: "P006",
    patient_name: "Sarah Miller",
    measure_id: "HEDIS-AMM-ACUTE",
    measure_name: "Antidepressant Medication Management",
    category: "behavioral_health",
    missing_element: "Antidepressant discontinued after 42 days",
    missing_codes: [],
    due_date: "2024-12-31",
    priority: "critical",
    days_overdue: 0,
    last_performed: null,
    recommendation: "Contact patient. Acute phase requires 84 days of treatment.",
    patient_instructions: "It's important to continue your antidepressant medication. Please contact us.",
    attributed_provider_id: "DR003",
    attributed_provider_name: "Dr. Emily Rodriguez",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-007",
    patient_id: "P007",
    patient_name: "Michael Davis",
    measure_id: "CQM-IMM-FLU",
    measure_name: "Adult Immunization: Influenza",
    category: "preventive",
    missing_element: "No flu vaccine this season",
    missing_codes: ["90686", "90688"],
    due_date: "2025-03-31",
    priority: "medium",
    days_overdue: 0,
    last_performed: "2023-10-15",
    recommendation: "Offer influenza vaccination during visit.",
    patient_instructions: "Please schedule your annual flu shot.",
    attributed_provider_id: "DR001",
    attributed_provider_name: "Dr. Sarah Johnson",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-008",
    patient_id: "P008",
    patient_name: "Jennifer Wilson",
    measure_id: "HEDIS-KED",
    measure_name: "Kidney Health Evaluation for Diabetes",
    category: "diabetes",
    missing_element: "Missing uACR test (eGFR completed)",
    missing_codes: ["82043", "82044"],
    due_date: "2024-12-31",
    priority: "high",
    days_overdue: 0,
    last_performed: null,
    recommendation: "Order urine albumin-to-creatinine ratio test.",
    patient_instructions: "You need a urine test to check your kidney health.",
    attributed_provider_id: "DR002",
    attributed_provider_name: "Dr. Michael Chen",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-009",
    patient_id: "P009",
    patient_name: "James Anderson",
    measure_id: "HEDIS-SPC",
    measure_name: "Statin Therapy for Cardiovascular Disease",
    category: "cardiovascular",
    missing_element: "No statin prescription for patient with ASCVD",
    missing_codes: [],
    due_date: "2024-12-31",
    priority: "critical",
    days_overdue: 0,
    last_performed: null,
    recommendation: "Prescribe high-intensity statin unless contraindicated.",
    patient_instructions: "Your provider would like to discuss cholesterol medication with you.",
    attributed_provider_id: "DR004",
    attributed_provider_name: "Dr. James Park",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-010",
    patient_id: "P010",
    patient_name: "Patricia Martinez",
    measure_id: "HEDIS-AWC",
    measure_name: "Annual Wellness Visit",
    category: "preventive",
    missing_element: "No wellness visit in current year",
    missing_codes: ["G0438", "G0439"],
    due_date: "2024-12-31",
    priority: "low",
    days_overdue: 0,
    last_performed: "2023-11-20",
    recommendation: "Schedule Medicare Annual Wellness Visit.",
    patient_instructions: "You are due for your annual wellness exam.",
    attributed_provider_id: "DR004",
    attributed_provider_name: "Dr. James Park",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-011",
    patient_id: "P011",
    patient_name: "William Taylor",
    measure_id: "HEDIS-CDC-HBA1C",
    measure_name: "Diabetes: HbA1c Control (<8%)",
    category: "diabetes",
    missing_element: "HbA1c 9.2% (target: <8%)",
    missing_codes: ["83036"],
    due_date: "2024-12-31",
    priority: "critical",
    days_overdue: 0,
    last_performed: "2024-11-01",
    recommendation: "Intensify diabetes management. Consider medication adjustment.",
    patient_instructions: "Your diabetes control needs improvement. Please schedule an appointment.",
    attributed_provider_id: "DR001",
    attributed_provider_name: "Dr. Sarah Johnson",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
  {
    id: "gap-012",
    patient_id: "P012",
    patient_name: "Elizabeth Thomas",
    measure_id: "HEDIS-CCS",
    measure_name: "Cervical Cancer Screening",
    category: "womens_health",
    missing_element: "Pap smear overdue (last: 2021-03-15)",
    missing_codes: ["88141", "88142"],
    due_date: "2024-03-15",
    priority: "high",
    days_overdue: 280,
    last_performed: "2021-03-15",
    recommendation: "Schedule cervical cancer screening.",
    patient_instructions: "You are overdue for your Pap smear. Please schedule an appointment.",
    attributed_provider_id: "DR002",
    attributed_provider_name: "Dr. Michael Chen",
    status: "open",
    scheduled_date: null,
    closed_date: null,
    closed_by: null,
  },
];

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

const getPriorityColor = (priority: string): string => {
  switch (priority) {
    case "critical":
      return "bg-red-600 text-white";
    case "high":
      return "bg-red-500 text-white";
    case "medium":
      return "bg-amber-500 text-white";
    case "low":
      return "bg-blue-500 text-white";
    default:
      return "bg-gray-500 text-white";
  }
};

const getPriorityBorderColor = (priority: string): string => {
  switch (priority) {
    case "critical":
      return "border-l-red-600";
    case "high":
      return "border-l-red-500";
    case "medium":
      return "border-l-amber-500";
    case "low":
      return "border-l-blue-500";
    default:
      return "border-l-gray-500";
  }
};

// ============================================================================
// Main Component
// ============================================================================

export default function PatientGapsPage() {
  const searchParams = useSearchParams();
  const initialMeasure = searchParams.get("measure") || "";

  const [gaps, setGaps] = useState<PatientGap[]>(mockGaps);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [measureFilter, setMeasureFilter] = useState<string>(initialMeasure || "all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [providerFilter, setProviderFilter] = useState<string>("all");
  const [selectedGaps, setSelectedGaps] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [outreachDialogOpen, setOutreachDialogOpen] = useState(false);
  const [selectedGapForAction, setSelectedGapForAction] = useState<PatientGap | null>(null);
  const [closureReason, setClosureReason] = useState("");
  const [closureNotes, setClosureNotes] = useState("");
  const pageSize = 20;

  // Get unique values for filters
  const measures = useMemo(() => {
    return ["all", ...new Set(gaps.map(g => g.measure_id))];
  }, [gaps]);

  const categories = useMemo(() => {
    return ["all", ...new Set(gaps.map(g => g.category))];
  }, [gaps]);

  const providers = useMemo(() => {
    return ["all", ...new Set(gaps.filter(g => g.attributed_provider_name).map(g => g.attributed_provider_id!))];
  }, [gaps]);

  // Filter gaps
  const filteredGaps = useMemo(() => {
    return gaps.filter(g => {
      const matchesSearch = searchQuery === "" ||
        g.patient_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        g.patient_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        g.measure_name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesMeasure = measureFilter === "all" || g.measure_id === measureFilter;
      const matchesCategory = categoryFilter === "all" || g.category === categoryFilter;
      const matchesPriority = priorityFilter === "all" || g.priority === priorityFilter;
      const matchesProvider = providerFilter === "all" || g.attributed_provider_id === providerFilter;
      return matchesSearch && matchesMeasure && matchesCategory && matchesPriority && matchesProvider;
    });
  }, [gaps, searchQuery, measureFilter, categoryFilter, priorityFilter, providerFilter]);

  // Pagination
  const totalPages = Math.ceil(filteredGaps.length / pageSize);
  const paginatedGaps = filteredGaps.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  // Summary counts
  const totalCritical = filteredGaps.filter(g => g.priority === "critical").length;
  const totalHigh = filteredGaps.filter(g => g.priority === "high").length;
  const totalMedium = filteredGaps.filter(g => g.priority === "medium").length;
  const totalLow = filteredGaps.filter(g => g.priority === "low").length;

  // Selection handlers
  const toggleSelectAll = () => {
    if (selectedGaps.size === paginatedGaps.length) {
      setSelectedGaps(new Set());
    } else {
      setSelectedGaps(new Set(paginatedGaps.map(g => g.id)));
    }
  };

  const toggleSelect = (gapId: string) => {
    const newSelected = new Set(selectedGaps);
    if (newSelected.has(gapId)) {
      newSelected.delete(gapId);
    } else {
      newSelected.add(gapId);
    }
    setSelectedGaps(newSelected);
  };

  // Export handler
  const handleExport = () => {
    const exportData = {
      exported_at: new Date().toISOString(),
      filters: {
        measure: measureFilter,
        category: categoryFilter,
        priority: priorityFilter,
        provider: providerFilter,
      },
      summary: {
        total: filteredGaps.length,
        critical: totalCritical,
        high: totalHigh,
        medium: totalMedium,
        low: totalLow,
      },
      gaps: filteredGaps,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `patient-gaps-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Close gap handler
  const handleCloseGap = () => {
    if (!selectedGapForAction) return;

    // In production, this would call the API
    setGaps(prev =>
      prev.map(g =>
        g.id === selectedGapForAction.id
          ? { ...g, status: "closed", closed_date: new Date().toISOString().split("T")[0], closed_by: "current_user" }
          : g
      )
    );
    setCloseDialogOpen(false);
    setSelectedGapForAction(null);
    setClosureReason("");
    setClosureNotes("");
  };

  // Bulk outreach handler
  const handleBulkOutreach = () => {
    // In production, this would trigger outreach workflows
    alert(`Bulk outreach initiated for ${selectedGaps.size} patients`);
    setOutreachDialogOpen(false);
    setSelectedGaps(new Set());
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/quality/measures">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Patient Care Gaps</h1>
            <p className="text-muted-foreground">
              Identify and address patients with missing quality measure requirements
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={selectedGaps.size === 0}
            onClick={() => setOutreachDialogOpen(true)}
          >
            <Send className="mr-2 h-4 w-4" />
            Bulk Outreach ({selectedGaps.size})
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Gaps</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{filteredGaps.length.toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-red-600">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Critical</CardTitle>
            <XCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{totalCritical}</div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-red-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">High</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-500">{totalHigh}</div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-amber-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Medium</CardTitle>
            <Clock className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-500">{totalMedium}</div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-blue-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Low</CardTitle>
            <CheckCircle className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-500">{totalLow}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search patients or measures..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            className="pl-8"
          />
        </div>

        <Select
          value={measureFilter}
          onValueChange={(v) => {
            setMeasureFilter(v);
            setCurrentPage(1);
          }}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Measure" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Measures</SelectItem>
            {measures.filter(m => m !== "all").map((m) => (
              <SelectItem key={m} value={m}>{m}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={categoryFilter}
          onValueChange={(v) => {
            setCategoryFilter(v);
            setCurrentPage(1);
          }}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {categories.filter(c => c !== "all").map((cat) => (
              <SelectItem key={cat} value={cat}>{getCategoryLabel(cat)}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={priorityFilter}
          onValueChange={(v) => {
            setPriorityFilter(v);
            setCurrentPage(1);
          }}
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Priorities</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={providerFilter}
          onValueChange={(v) => {
            setProviderFilter(v);
            setCurrentPage(1);
          }}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Provider" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Providers</SelectItem>
            {gaps
              .filter(g => g.attributed_provider_id)
              .reduce((acc, g) => {
                if (!acc.some(a => a.id === g.attributed_provider_id)) {
                  acc.push({ id: g.attributed_provider_id!, name: g.attributed_provider_name! });
                }
                return acc;
              }, [] as { id: string; name: string }[])
              .map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
              ))}
          </SelectContent>
        </Select>
      </div>

      {/* Gaps Table */}
      <Card>
        <CardHeader>
          <CardTitle>Patient Care Gaps</CardTitle>
          <CardDescription>
            {filteredGaps.length.toLocaleString()} gaps found - sorted by priority and due date
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <Checkbox
                    checked={selectedGaps.size === paginatedGaps.length && paginatedGaps.length > 0}
                    onCheckedChange={toggleSelectAll}
                  />
                </TableHead>
                <TableHead>Patient</TableHead>
                <TableHead>Measure</TableHead>
                <TableHead>Missing Element</TableHead>
                <TableHead>Due Date</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedGaps.map((gap) => (
                <TableRow
                  key={gap.id}
                  className={`border-l-4 ${getPriorityBorderColor(gap.priority)}`}
                >
                  <TableCell>
                    <Checkbox
                      checked={selectedGaps.has(gap.id)}
                      onCheckedChange={() => toggleSelect(gap.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <div>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">{gap.patient_name || "Unknown"}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">{gap.patient_id}</div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div>
                      <div className="flex items-center gap-2">
                        {getCategoryIcon(gap.category)}
                        <span className="font-medium text-sm">{gap.measure_name}</span>
                      </div>
                      <Badge variant="outline" className="text-xs mt-1">
                        {getCategoryLabel(gap.category)}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="max-w-[250px]">
                      <div className="text-sm">{gap.missing_element}</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {gap.recommendation}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Calendar className="h-3 w-3 text-muted-foreground" />
                      <span className="text-sm">{gap.due_date}</span>
                    </div>
                    {gap.days_overdue > 0 && (
                      <div className="text-xs text-red-600 font-medium">
                        {gap.days_overdue} days overdue
                      </div>
                    )}
                    {gap.last_performed && (
                      <div className="text-xs text-muted-foreground">
                        Last: {gap.last_performed}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge className={getPriorityColor(gap.priority)}>
                      {gap.priority}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {gap.attributed_provider_name && (
                      <div className="text-sm">{gap.attributed_provider_name}</div>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Link href={`/patients/${gap.patient_id}/graph`}>
                        <Button variant="ghost" size="sm">
                          <User className="h-4 w-4" />
                        </Button>
                      </Link>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedGapForAction(gap);
                          setCloseDialogOpen(true);
                        }}
                      >
                        <CheckCircle className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}

              {paginatedGaps.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-12">
                    <div className="flex flex-col items-center text-muted-foreground">
                      <CheckCircle className="h-12 w-12 mb-2 opacity-50" />
                      <p>No gaps match your filters</p>
                      <Button
                        variant="link"
                        onClick={() => {
                          setSearchQuery("");
                          setMeasureFilter("all");
                          setCategoryFilter("all");
                          setPriorityFilter("all");
                          setProviderFilter("all");
                        }}
                      >
                        Clear filters
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                Showing {(currentPage - 1) * pageSize + 1} to{" "}
                {Math.min(currentPage * pageSize, filteredGaps.length)} of{" "}
                {filteredGaps.length} gaps
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Close Gap Dialog */}
      <Dialog open={closeDialogOpen} onOpenChange={setCloseDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Close Care Gap</DialogTitle>
            <DialogDescription>
              Mark this care gap as closed for{" "}
              <strong>{selectedGapForAction?.patient_name}</strong> -{" "}
              {selectedGapForAction?.measure_name}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="closure-reason">Closure Reason</Label>
              <Select value={closureReason} onValueChange={setClosureReason}>
                <SelectTrigger>
                  <SelectValue placeholder="Select reason" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="completed">Service Completed</SelectItem>
                  <SelectItem value="documented">Previously Documented</SelectItem>
                  <SelectItem value="excluded">Patient Excluded</SelectItem>
                  <SelectItem value="refused">Patient Refused</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="closure-notes">Notes (Optional)</Label>
              <Textarea
                id="closure-notes"
                placeholder="Add any additional notes..."
                value={closureNotes}
                onChange={(e) => setClosureNotes(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCloseDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCloseGap} disabled={!closureReason}>
              <CheckCircle className="mr-2 h-4 w-4" />
              Close Gap
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Outreach Dialog */}
      <Dialog open={outreachDialogOpen} onOpenChange={setOutreachDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Bulk Patient Outreach</DialogTitle>
            <DialogDescription>
              Send outreach communications to {selectedGaps.size} selected patients
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="rounded-lg border p-4 bg-muted/50">
              <div className="flex items-center gap-2 mb-2">
                <MessageSquare className="h-5 w-5" />
                <span className="font-medium">Outreach Summary</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Patients:</span>{" "}
                  <span className="font-medium">{selectedGaps.size}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Critical:</span>{" "}
                  <span className="font-medium text-red-600">
                    {[...selectedGaps].filter(id => gaps.find(g => g.id === id)?.priority === "critical").length}
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Outreach Method</Label>
              <div className="grid grid-cols-3 gap-2">
                <Button variant="outline" className="h-auto py-3 flex-col gap-1">
                  <Phone className="h-5 w-5" />
                  <span className="text-xs">Phone Call</span>
                </Button>
                <Button variant="outline" className="h-auto py-3 flex-col gap-1">
                  <Mail className="h-5 w-5" />
                  <span className="text-xs">Email</span>
                </Button>
                <Button variant="outline" className="h-auto py-3 flex-col gap-1">
                  <FileText className="h-5 w-5" />
                  <span className="text-xs">Letter</span>
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOutreachDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleBulkOutreach}>
              <Send className="mr-2 h-4 w-4" />
              Send Outreach
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
