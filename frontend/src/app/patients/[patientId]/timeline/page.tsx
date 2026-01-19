"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Clock,
  Calendar,
  Activity,
  Pill,
  Stethoscope,
  FileText,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  Filter,
  Heart,
  Thermometer,
  Syringe,
  Scissors,
  Eye,
  ArrowLeft,
  Maximize2,
  X,
} from "lucide-react";

// Types
type EventType = "condition" | "medication" | "procedure" | "visit" | "observation" | "immunization";

interface TimelineEvent {
  id: string;
  type: EventType;
  title: string;
  description: string;
  date: string;
  endDate?: string;
  status: "active" | "completed" | "discontinued" | "scheduled";
  severity?: "mild" | "moderate" | "severe";
  codes?: { system: string; code: string; display: string }[];
  details?: Record<string, unknown>;
  provider?: string;
  location?: string;
}

interface TimelineFilters {
  conditions: boolean;
  medications: boolean;
  procedures: boolean;
  visits: boolean;
  observations: boolean;
  immunizations: boolean;
}

// Mock Data
const mockEvents: TimelineEvent[] = [
  {
    id: "event-001",
    type: "visit",
    title: "Annual Physical Examination",
    description: "Routine annual health assessment with comprehensive metabolic panel",
    date: "2026-01-15",
    status: "completed",
    codes: [{ system: "CPT", code: "99395", display: "Preventive visit, 18-39" }],
    provider: "Dr. John Smith",
    location: "Main Clinic",
    details: { vitals: { bp: "122/78", pulse: 72, weight: "175 lbs" } },
  },
  {
    id: "event-002",
    type: "condition",
    title: "Type 2 Diabetes Mellitus",
    description: "Diagnosed with T2DM, starting on metformin therapy",
    date: "2025-11-20",
    status: "active",
    severity: "moderate",
    codes: [{ system: "ICD-10", code: "E11.9", display: "Type 2 diabetes mellitus without complications" }],
    provider: "Dr. Sarah Davis",
  },
  {
    id: "event-003",
    type: "medication",
    title: "Metformin 500mg",
    description: "Started metformin for diabetes management, twice daily",
    date: "2025-11-20",
    status: "active",
    codes: [{ system: "RxNorm", code: "861007", display: "Metformin 500mg tablet" }],
    details: { dosage: "500mg", frequency: "BID", route: "oral" },
  },
  {
    id: "event-004",
    type: "observation",
    title: "HbA1c: 7.2%",
    description: "Hemoglobin A1c test result showing improved glycemic control",
    date: "2025-12-15",
    status: "completed",
    codes: [{ system: "LOINC", code: "4548-4", display: "Hemoglobin A1c" }],
    details: { value: 7.2, unit: "%", reference_range: "< 5.7%" },
  },
  {
    id: "event-005",
    type: "visit",
    title: "Diabetes Follow-up",
    description: "3-month follow-up for diabetes management review",
    date: "2025-12-15",
    status: "completed",
    codes: [{ system: "CPT", code: "99213", display: "Office visit, established patient" }],
    provider: "Dr. Sarah Davis",
    location: "Endocrinology Clinic",
  },
  {
    id: "event-006",
    type: "condition",
    title: "Essential Hypertension",
    description: "Elevated blood pressure readings over multiple visits",
    date: "2025-08-10",
    status: "active",
    severity: "mild",
    codes: [{ system: "ICD-10", code: "I10", display: "Essential hypertension" }],
    provider: "Dr. John Smith",
  },
  {
    id: "event-007",
    type: "medication",
    title: "Lisinopril 10mg",
    description: "ACE inhibitor for hypertension management",
    date: "2025-08-10",
    status: "active",
    codes: [{ system: "RxNorm", code: "314076", display: "Lisinopril 10mg tablet" }],
    details: { dosage: "10mg", frequency: "QD", route: "oral" },
  },
  {
    id: "event-008",
    type: "procedure",
    title: "Colonoscopy",
    description: "Screening colonoscopy, no polyps found",
    date: "2025-06-22",
    status: "completed",
    codes: [{ system: "CPT", code: "45378", display: "Colonoscopy, diagnostic" }],
    provider: "Dr. Michael Chen",
    location: "Outpatient Surgery Center",
    details: { findings: "Normal mucosa, no polyps", prep: "MiraLAX/Gatorade" },
  },
  {
    id: "event-009",
    type: "immunization",
    title: "Influenza Vaccine",
    description: "Annual flu vaccination, quadrivalent",
    date: "2025-10-05",
    status: "completed",
    codes: [{ system: "CVX", code: "197", display: "Influenza, high-dose, quadrivalent" }],
    provider: "Nurse Amy Wilson",
    location: "Main Clinic",
  },
  {
    id: "event-010",
    type: "condition",
    title: "Osteoarthritis, Knee",
    description: "Degenerative joint disease of left knee",
    date: "2024-03-15",
    status: "active",
    severity: "moderate",
    codes: [{ system: "ICD-10", code: "M17.12", display: "Primary osteoarthritis, left knee" }],
    provider: "Dr. Robert Johnson",
  },
  {
    id: "event-011",
    type: "procedure",
    title: "Knee X-ray",
    description: "Radiographic imaging of left knee",
    date: "2024-03-15",
    status: "completed",
    codes: [{ system: "CPT", code: "73562", display: "X-ray exam of knee, 3 views" }],
    provider: "Radiology Department",
    location: "Imaging Center",
    details: { findings: "Moderate joint space narrowing, osteophyte formation" },
  },
  {
    id: "event-012",
    type: "medication",
    title: "Ibuprofen 400mg PRN",
    description: "NSAID for knee pain as needed",
    date: "2024-03-15",
    endDate: "2025-06-01",
    status: "discontinued",
    codes: [{ system: "RxNorm", code: "197806", display: "Ibuprofen 400mg tablet" }],
    details: { dosage: "400mg", frequency: "TID PRN", route: "oral", reason_discontinued: "GI upset" },
  },
  {
    id: "event-013",
    type: "visit",
    title: "Urgent Care Visit",
    description: "Upper respiratory infection",
    date: "2025-02-08",
    status: "completed",
    codes: [{ system: "CPT", code: "99214", display: "Office visit, established patient" }],
    provider: "Dr. Lisa Martinez",
    location: "Urgent Care",
    details: { diagnosis: "Acute sinusitis", treatment: "Amoxicillin 875mg BID x 10 days" },
  },
  {
    id: "event-014",
    type: "observation",
    title: "Blood Pressure: 128/82",
    description: "Routine blood pressure measurement",
    date: "2026-01-15",
    status: "completed",
    codes: [{ system: "LOINC", code: "85354-9", display: "Blood pressure panel" }],
    details: { systolic: 128, diastolic: 82, position: "seated" },
  },
  {
    id: "event-015",
    type: "immunization",
    title: "COVID-19 Vaccine Booster",
    description: "Updated COVID-19 booster vaccination",
    date: "2025-09-15",
    status: "completed",
    codes: [{ system: "CVX", code: "308", display: "COVID-19, bivalent" }],
    provider: "Pharmacy",
    location: "CVS Pharmacy",
  },
];

// Helper functions
const getEventIcon = (type: EventType) => {
  switch (type) {
    case "condition":
      return <Heart className="h-4 w-4" />;
    case "medication":
      return <Pill className="h-4 w-4" />;
    case "procedure":
      return <Scissors className="h-4 w-4" />;
    case "visit":
      return <Stethoscope className="h-4 w-4" />;
    case "observation":
      return <Thermometer className="h-4 w-4" />;
    case "immunization":
      return <Syringe className="h-4 w-4" />;
    default:
      return <Activity className="h-4 w-4" />;
  }
};

const getEventColor = (type: EventType): string => {
  switch (type) {
    case "condition":
      return "bg-red-500";
    case "medication":
      return "bg-blue-500";
    case "procedure":
      return "bg-purple-500";
    case "visit":
      return "bg-green-500";
    case "observation":
      return "bg-amber-500";
    case "immunization":
      return "bg-cyan-500";
    default:
      return "bg-gray-500";
  }
};

const getEventBadgeColor = (type: EventType): string => {
  switch (type) {
    case "condition":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    case "medication":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "procedure":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    case "visit":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "observation":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "immunization":
      return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
  }
};

const getStatusBadge = (status: string) => {
  switch (status) {
    case "active":
      return <Badge className="bg-green-500 text-white">Active</Badge>;
    case "completed":
      return <Badge variant="secondary">Completed</Badge>;
    case "discontinued":
      return <Badge variant="outline">Discontinued</Badge>;
    case "scheduled":
      return <Badge className="bg-blue-500 text-white">Scheduled</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
};

const getSeverityBadge = (severity?: string) => {
  if (!severity) return null;
  switch (severity) {
    case "mild":
      return <Badge className="bg-yellow-100 text-yellow-800">Mild</Badge>;
    case "moderate":
      return <Badge className="bg-orange-100 text-orange-800">Moderate</Badge>;
    case "severe":
      return <Badge className="bg-red-100 text-red-800">Severe</Badge>;
    default:
      return null;
  }
};

const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const groupEventsByMonth = (events: TimelineEvent[]): Map<string, TimelineEvent[]> => {
  const grouped = new Map<string, TimelineEvent[]>();
  events.forEach((event) => {
    const monthYear = new Date(event.date).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
    });
    const existing = grouped.get(monthYear) || [];
    grouped.set(monthYear, [...existing, event]);
  });
  return grouped;
};

type ZoomLevel = "1m" | "3m" | "6m" | "1y" | "all";

export default function PatientTimelinePage() {
  const params = useParams();
  const patientId = params.patientId as string;

  const [events] = useState<TimelineEvent[]>(mockEvents);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>("1y");
  const [filters, setFilters] = useState<TimelineFilters>({
    conditions: true,
    medications: true,
    procedures: true,
    visits: true,
    observations: true,
    immunizations: true,
  });

  // Calculate date range based on zoom level
  const dateRange = useMemo(() => {
    const now = new Date();
    const endDate = now;
    let startDate: Date;

    switch (zoomLevel) {
      case "1m":
        startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
        break;
      case "3m":
        startDate = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
        break;
      case "6m":
        startDate = new Date(now.getFullYear(), now.getMonth() - 6, now.getDate());
        break;
      case "1y":
        startDate = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
        break;
      case "all":
      default:
        startDate = new Date(2000, 0, 1);
        break;
    }

    return { startDate, endDate };
  }, [zoomLevel]);

  // Filter and sort events
  const filteredEvents = useMemo(() => {
    return events
      .filter((event) => {
        // Filter by type
        const typeFilter = filters[`${event.type}s` as keyof TimelineFilters];
        if (!typeFilter) return false;

        // Filter by date range
        const eventDate = new Date(event.date);
        if (eventDate < dateRange.startDate || eventDate > dateRange.endDate) {
          return false;
        }

        return true;
      })
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [events, filters, dateRange]);

  const groupedEvents = useMemo(() => {
    return groupEventsByMonth(filteredEvents);
  }, [filteredEvents]);

  const toggleFilter = (key: keyof TimelineFilters) => {
    setFilters({ ...filters, [key]: !filters[key] });
  };

  const selectAllFilters = () => {
    setFilters({
      conditions: true,
      medications: true,
      procedures: true,
      visits: true,
      observations: true,
      immunizations: true,
    });
  };

  const clearAllFilters = () => {
    setFilters({
      conditions: false,
      medications: false,
      procedures: false,
      visits: false,
      observations: false,
      immunizations: false,
    });
  };

  const refreshData = async () => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsLoading(false);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Link href={`/patients/${patientId}/graph`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Patient
              </Button>
            </Link>
          </div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Clock className="h-6 w-6" />
            Patient Timeline
          </h1>
          <p className="text-muted-foreground">
            Visual timeline of patient events for ID: {patientId}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        <Card className="cursor-pointer hover:bg-muted/50" onClick={() => toggleFilter("conditions")}>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-full ${filters.conditions ? "bg-red-100" : "bg-gray-100"}`}>
                <Heart className={`h-4 w-4 ${filters.conditions ? "text-red-600" : "text-gray-400"}`} />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {events.filter((e) => e.type === "condition").length}
                </div>
                <p className="text-xs text-muted-foreground">Conditions</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50" onClick={() => toggleFilter("medications")}>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-full ${filters.medications ? "bg-blue-100" : "bg-gray-100"}`}>
                <Pill className={`h-4 w-4 ${filters.medications ? "text-blue-600" : "text-gray-400"}`} />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {events.filter((e) => e.type === "medication").length}
                </div>
                <p className="text-xs text-muted-foreground">Medications</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50" onClick={() => toggleFilter("procedures")}>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-full ${filters.procedures ? "bg-purple-100" : "bg-gray-100"}`}>
                <Scissors className={`h-4 w-4 ${filters.procedures ? "text-purple-600" : "text-gray-400"}`} />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {events.filter((e) => e.type === "procedure").length}
                </div>
                <p className="text-xs text-muted-foreground">Procedures</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50" onClick={() => toggleFilter("visits")}>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-full ${filters.visits ? "bg-green-100" : "bg-gray-100"}`}>
                <Stethoscope className={`h-4 w-4 ${filters.visits ? "text-green-600" : "text-gray-400"}`} />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {events.filter((e) => e.type === "visit").length}
                </div>
                <p className="text-xs text-muted-foreground">Visits</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50" onClick={() => toggleFilter("observations")}>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-full ${filters.observations ? "bg-amber-100" : "bg-gray-100"}`}>
                <Thermometer className={`h-4 w-4 ${filters.observations ? "text-amber-600" : "text-gray-400"}`} />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {events.filter((e) => e.type === "observation").length}
                </div>
                <p className="text-xs text-muted-foreground">Observations</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50" onClick={() => toggleFilter("immunizations")}>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-full ${filters.immunizations ? "bg-cyan-100" : "bg-gray-100"}`}>
                <Syringe className={`h-4 w-4 ${filters.immunizations ? "text-cyan-600" : "text-gray-400"}`} />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {events.filter((e) => e.type === "immunization").length}
                </div>
                <p className="text-xs text-muted-foreground">Immunizations</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            {/* Zoom Controls */}
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Time Range:</span>
              <div className="flex gap-1">
                {(["1m", "3m", "6m", "1y", "all"] as ZoomLevel[]).map((level) => (
                  <Button
                    key={level}
                    variant={zoomLevel === level ? "default" : "outline"}
                    size="sm"
                    onClick={() => setZoomLevel(level)}
                  >
                    {level === "all" ? "All" : level.toUpperCase()}
                  </Button>
                ))}
              </div>
            </div>

            {/* Filter Controls */}
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={selectAllFilters}>
                Select All
              </Button>
              <Button variant="ghost" size="sm" onClick={clearAllFilters}>
                Clear All
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-4">
            {(Object.keys(filters) as (keyof TimelineFilters)[]).map((key) => (
              <div key={key} className="flex items-center space-x-2">
                <Checkbox
                  id={`filter-${key}`}
                  checked={filters[key]}
                  onCheckedChange={() => toggleFilter(key)}
                />
                <Label htmlFor={`filter-${key}`} className="capitalize text-sm">
                  {key}
                </Label>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Timeline
          </CardTitle>
          <CardDescription>
            Showing {filteredEvents.length} events from{" "}
            {dateRange.startDate.toLocaleDateString()} to{" "}
            {dateRange.endDate.toLocaleDateString()}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertCircle className="h-12 w-12 text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-medium">No Events Found</h3>
              <p className="text-sm text-muted-foreground">
                Adjust filters or time range to see events
              </p>
            </div>
          ) : (
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border" />

              <div className="space-y-8">
                {Array.from(groupedEvents.entries()).map(([monthYear, monthEvents]) => (
                  <div key={monthYear}>
                    {/* Month Header */}
                    <div className="flex items-center gap-4 mb-4">
                      <div className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full bg-background border-2 border-primary">
                        <Calendar className="h-4 w-4 text-primary" />
                      </div>
                      <h3 className="text-lg font-semibold">{monthYear}</h3>
                    </div>

                    {/* Events for this month */}
                    <div className="space-y-4 ml-4">
                      {monthEvents.map((event) => (
                        <div
                          key={event.id}
                          className="relative flex gap-4 cursor-pointer group"
                          onClick={() => setSelectedEvent(event)}
                        >
                          {/* Event dot */}
                          <div
                            className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full text-white ${getEventColor(
                              event.type
                            )}`}
                          >
                            {getEventIcon(event.type)}
                          </div>

                          {/* Event card */}
                          <div className="flex-1 rounded-lg border p-4 hover:bg-muted/50 transition-colors">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <h4 className="font-medium">{event.title}</h4>
                                  <Badge className={getEventBadgeColor(event.type)}>
                                    {event.type}
                                  </Badge>
                                  {getStatusBadge(event.status)}
                                  {getSeverityBadge(event.severity)}
                                </div>
                                <p className="text-sm text-muted-foreground mt-1">
                                  {event.description}
                                </p>
                                <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                                  <span className="flex items-center gap-1">
                                    <Calendar className="h-3 w-3" />
                                    {formatDate(event.date)}
                                    {event.endDate && ` - ${formatDate(event.endDate)}`}
                                  </span>
                                  {event.provider && (
                                    <span>{event.provider}</span>
                                  )}
                                  {event.location && (
                                    <span>{event.location}</span>
                                  )}
                                </div>
                                {event.codes && event.codes.length > 0 && (
                                  <div className="flex flex-wrap gap-1 mt-2">
                                    {event.codes.map((code, idx) => (
                                      <code
                                        key={idx}
                                        className="text-xs bg-muted px-1.5 py-0.5 rounded"
                                      >
                                        {code.system}: {code.code}
                                      </code>
                                    ))}
                                  </div>
                                )}
                              </div>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="opacity-0 group-hover:opacity-100 transition-opacity"
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Event Detail Dialog */}
      <Dialog open={!!selectedEvent} onOpenChange={() => setSelectedEvent(null)}>
        <DialogContent className="max-w-lg">
          {selectedEvent && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-2">
                  <div
                    className={`p-2 rounded-full text-white ${getEventColor(
                      selectedEvent.type
                    )}`}
                  >
                    {getEventIcon(selectedEvent.type)}
                  </div>
                  <div>
                    <DialogTitle>{selectedEvent.title}</DialogTitle>
                    <DialogDescription>
                      {formatDate(selectedEvent.date)}
                      {selectedEvent.endDate &&
                        ` - ${formatDate(selectedEvent.endDate)}`}
                    </DialogDescription>
                  </div>
                </div>
              </DialogHeader>
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge className={getEventBadgeColor(selectedEvent.type)}>
                    {selectedEvent.type}
                  </Badge>
                  {getStatusBadge(selectedEvent.status)}
                  {getSeverityBadge(selectedEvent.severity)}
                </div>

                <div>
                  <h4 className="text-sm font-medium mb-1">Description</h4>
                  <p className="text-sm text-muted-foreground">
                    {selectedEvent.description}
                  </p>
                </div>

                {selectedEvent.codes && selectedEvent.codes.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-1">Codes</h4>
                    <div className="space-y-1">
                      {selectedEvent.codes.map((code, idx) => (
                        <div key={idx} className="text-sm">
                          <code className="bg-muted px-1.5 py-0.5 rounded">
                            {code.system}: {code.code}
                          </code>
                          <span className="text-muted-foreground ml-2">
                            {code.display}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {(selectedEvent.provider || selectedEvent.location) && (
                  <div className="grid gap-2 md:grid-cols-2">
                    {selectedEvent.provider && (
                      <div>
                        <h4 className="text-sm font-medium">Provider</h4>
                        <p className="text-sm text-muted-foreground">
                          {selectedEvent.provider}
                        </p>
                      </div>
                    )}
                    {selectedEvent.location && (
                      <div>
                        <h4 className="text-sm font-medium">Location</h4>
                        <p className="text-sm text-muted-foreground">
                          {selectedEvent.location}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {selectedEvent.details && (
                  <div>
                    <h4 className="text-sm font-medium mb-1">Details</h4>
                    <pre className="text-xs bg-muted p-3 rounded overflow-auto">
                      {JSON.stringify(selectedEvent.details, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
