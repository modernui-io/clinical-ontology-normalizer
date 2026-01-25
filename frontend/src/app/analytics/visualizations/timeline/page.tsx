"use client";

import { useState, useMemo } from "react";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Calendar,
  Clock,
  Users,
  FileText,
  AlertCircle,
  CheckCircle2,
  PlayCircle,
  PauseCircle,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Target,
  Flag,
  Milestone,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

type TaskStatus = "not_started" | "in_progress" | "completed" | "delayed" | "blocked";
type TaskCategory = "enrollment" | "treatment" | "followup" | "analysis" | "regulatory" | "milestone";

interface StudyTask {
  id: string;
  name: string;
  category: TaskCategory;
  status: TaskStatus;
  startDate: string;
  endDate: string;
  plannedStartDate?: string;
  plannedEndDate?: string;
  progress: number;
  assignee?: string;
  dependencies?: string[];
  description?: string;
  isMilestone?: boolean;
}

interface StudyPhase {
  id: string;
  name: string;
  startDate: string;
  endDate: string;
  tasks: StudyTask[];
}

interface Study {
  id: string;
  name: string;
  sponsor: string;
  protocol: string;
  startDate: string;
  endDate: string;
  currentPhase: string;
  phases: StudyPhase[];
  enrollmentTarget: number;
  enrollmentCurrent: number;
}

// ============================================================================
// Mock Data
// ============================================================================

const mockStudy: Study = {
  id: "study-001",
  name: "BEACON Phase III Clinical Trial",
  sponsor: "Acme Pharmaceuticals",
  protocol: "ACME-2024-001",
  startDate: "2024-01-01",
  endDate: "2025-12-31",
  currentPhase: "Treatment",
  enrollmentTarget: 500,
  enrollmentCurrent: 342,
  phases: [
    {
      id: "phase-1",
      name: "Startup & Regulatory",
      startDate: "2024-01-01",
      endDate: "2024-03-31",
      tasks: [
        { id: "t1", name: "Protocol Finalization", category: "regulatory", status: "completed", startDate: "2024-01-01", endDate: "2024-01-31", progress: 100 },
        { id: "t2", name: "IRB Submission", category: "regulatory", status: "completed", startDate: "2024-02-01", endDate: "2024-02-15", progress: 100, dependencies: ["t1"] },
        { id: "t3", name: "IRB Approval", category: "milestone", status: "completed", startDate: "2024-02-28", endDate: "2024-02-28", progress: 100, isMilestone: true, dependencies: ["t2"] },
        { id: "t4", name: "Site Selection", category: "regulatory", status: "completed", startDate: "2024-02-01", endDate: "2024-03-15", progress: 100 },
        { id: "t5", name: "Site Initiation Visits", category: "regulatory", status: "completed", startDate: "2024-03-01", endDate: "2024-03-31", progress: 100, dependencies: ["t3", "t4"] },
      ],
    },
    {
      id: "phase-2",
      name: "Enrollment",
      startDate: "2024-04-01",
      endDate: "2024-09-30",
      tasks: [
        { id: "t6", name: "First Patient In", category: "milestone", status: "completed", startDate: "2024-04-15", endDate: "2024-04-15", progress: 100, isMilestone: true },
        { id: "t7", name: "Enrollment Period", category: "enrollment", status: "in_progress", startDate: "2024-04-15", endDate: "2024-09-30", plannedEndDate: "2024-08-31", progress: 68, assignee: "Clinical Ops" },
        { id: "t8", name: "25% Enrollment", category: "milestone", status: "completed", startDate: "2024-05-30", endDate: "2024-05-30", progress: 100, isMilestone: true },
        { id: "t9", name: "50% Enrollment", category: "milestone", status: "completed", startDate: "2024-07-15", endDate: "2024-07-15", progress: 100, isMilestone: true },
        { id: "t10", name: "Last Patient In", category: "milestone", status: "not_started", startDate: "2024-09-30", endDate: "2024-09-30", progress: 0, isMilestone: true },
      ],
    },
    {
      id: "phase-3",
      name: "Treatment",
      startDate: "2024-04-15",
      endDate: "2025-03-31",
      tasks: [
        { id: "t11", name: "Treatment Administration", category: "treatment", status: "in_progress", startDate: "2024-04-15", endDate: "2025-03-31", progress: 45, assignee: "Sites" },
        { id: "t12", name: "Safety Monitoring", category: "treatment", status: "in_progress", startDate: "2024-04-15", endDate: "2025-03-31", progress: 45, assignee: "Safety Team" },
        { id: "t13", name: "DSMB Review 1", category: "milestone", status: "completed", startDate: "2024-07-01", endDate: "2024-07-01", progress: 100, isMilestone: true },
        { id: "t14", name: "DSMB Review 2", category: "milestone", status: "not_started", startDate: "2024-12-01", endDate: "2024-12-01", progress: 0, isMilestone: true },
        { id: "t15", name: "Last Patient Out", category: "milestone", status: "not_started", startDate: "2025-03-31", endDate: "2025-03-31", progress: 0, isMilestone: true },
      ],
    },
    {
      id: "phase-4",
      name: "Follow-up",
      startDate: "2025-01-01",
      endDate: "2025-06-30",
      tasks: [
        { id: "t16", name: "Follow-up Visits", category: "followup", status: "not_started", startDate: "2025-01-01", endDate: "2025-06-30", progress: 0 },
        { id: "t17", name: "Data Collection", category: "followup", status: "not_started", startDate: "2025-01-01", endDate: "2025-06-30", progress: 0 },
      ],
    },
    {
      id: "phase-5",
      name: "Analysis & Closeout",
      startDate: "2025-07-01",
      endDate: "2025-12-31",
      tasks: [
        { id: "t18", name: "Database Lock", category: "milestone", status: "not_started", startDate: "2025-07-15", endDate: "2025-07-15", progress: 0, isMilestone: true },
        { id: "t19", name: "Statistical Analysis", category: "analysis", status: "not_started", startDate: "2025-07-15", endDate: "2025-09-30", progress: 0, assignee: "Biostatistics" },
        { id: "t20", name: "CSR Preparation", category: "analysis", status: "not_started", startDate: "2025-10-01", endDate: "2025-11-30", progress: 0 },
        { id: "t21", name: "Study Closeout", category: "regulatory", status: "not_started", startDate: "2025-12-01", endDate: "2025-12-31", progress: 0 },
      ],
    },
  ],
};

// ============================================================================
// Helper Functions
// ============================================================================

const getStatusColor = (status: TaskStatus) => {
  switch (status) {
    case "completed":
      return "bg-green-500";
    case "in_progress":
      return "bg-blue-500";
    case "delayed":
      return "bg-amber-500";
    case "blocked":
      return "bg-red-500";
    case "not_started":
    default:
      return "bg-gray-300 dark:bg-gray-600";
  }
};

const getStatusBadgeColor = (status: TaskStatus) => {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    case "in_progress":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
    case "delayed":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
    case "blocked":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
  }
};

const getCategoryColor = (category: TaskCategory) => {
  switch (category) {
    case "enrollment":
      return "border-purple-500 bg-purple-100 dark:bg-purple-900/30";
    case "treatment":
      return "border-blue-500 bg-blue-100 dark:bg-blue-900/30";
    case "followup":
      return "border-cyan-500 bg-cyan-100 dark:bg-cyan-900/30";
    case "analysis":
      return "border-amber-500 bg-amber-100 dark:bg-amber-900/30";
    case "regulatory":
      return "border-green-500 bg-green-100 dark:bg-green-900/30";
    case "milestone":
      return "border-red-500 bg-red-100 dark:bg-red-900/30";
    default:
      return "border-gray-500 bg-gray-100 dark:bg-gray-800";
  }
};

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

const getDaysBetween = (start: string, end: string) => {
  const startDate = new Date(start);
  const endDate = new Date(end);
  return Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
};

const getDaysFromStart = (date: string, studyStart: string) => {
  return getDaysBetween(studyStart, date);
};

// ============================================================================
// Gantt Bar Component
// ============================================================================

function GanttBar({ task, studyStart, totalDays, dayWidth }: { task: StudyTask; studyStart: string; totalDays: number; dayWidth: number }) {
  const startOffset = getDaysFromStart(task.startDate, studyStart) * dayWidth;
  const duration = getDaysBetween(task.startDate, task.endDate) || 1;
  const width = Math.max(duration * dayWidth, task.isMilestone ? 20 : 30);

  const today = new Date().toISOString().split("T")[0];
  const todayOffset = getDaysFromStart(today, studyStart) * dayWidth;

  if (task.isMilestone) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className="absolute flex items-center justify-center cursor-pointer transition-transform hover:scale-110"
              style={{ left: startOffset, top: "50%", transform: "translateY(-50%)" }}
            >
              <div
                className={`w-5 h-5 rotate-45 ${getStatusColor(task.status)} border-2 border-white dark:border-gray-800 shadow-md`}
              />
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <div className="space-y-1">
              <div className="font-medium">{task.name}</div>
              <div className="text-xs text-muted-foreground">{formatDate(task.startDate)}</div>
              <Badge className={getStatusBadgeColor(task.status)}>{task.status.replace("_", " ")}</Badge>
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={`absolute h-6 rounded cursor-pointer transition-all hover:brightness-110 ${getStatusColor(task.status)} shadow-sm`}
            style={{
              left: startOffset,
              width,
              top: "50%",
              transform: "translateY(-50%)",
            }}
          >
            {/* Progress indicator */}
            {task.progress > 0 && task.progress < 100 && (
              <div
                className="absolute inset-y-0 left-0 bg-white/30 rounded-l"
                style={{ width: `${task.progress}%` }}
              />
            )}
            {/* Task name (if wide enough) */}
            {width > 80 && (
              <span className="absolute inset-0 flex items-center justify-center text-xs text-white font-medium truncate px-2">
                {task.name}
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <div className="space-y-1">
            <div className="font-medium">{task.name}</div>
            <div className="text-xs text-muted-foreground">
              {formatDate(task.startDate)} - {formatDate(task.endDate)}
            </div>
            <div className="flex items-center gap-2">
              <Badge className={getStatusBadgeColor(task.status)}>{task.status.replace("_", " ")}</Badge>
              <span className="text-xs">{task.progress}% complete</span>
            </div>
            {task.assignee && <div className="text-xs">Assignee: {task.assignee}</div>}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function StudyTimelinePage() {
  const [study] = useState<Study>(mockStudy);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [viewMode, setViewMode] = useState<"phases" | "all">("phases");

  // Calculate timeline dimensions
  const totalDays = getDaysBetween(study.startDate, study.endDate);
  const dayWidth = 2 * zoomLevel;
  const totalWidth = totalDays * dayWidth;

  // Generate month markers
  const months = useMemo(() => {
    const result: { date: Date; label: string; offset: number }[] = [];
    const start = new Date(study.startDate);
    const end = new Date(study.endDate);
    const current = new Date(start.getFullYear(), start.getMonth(), 1);

    while (current <= end) {
      const offset = getDaysFromStart(current.toISOString().split("T")[0], study.startDate) * dayWidth;
      result.push({
        date: new Date(current),
        label: current.toLocaleDateString("en-US", { month: "short", year: "2-digit" }),
        offset: Math.max(0, offset),
      });
      current.setMonth(current.getMonth() + 1);
    }
    return result;
  }, [study.startDate, study.endDate, dayWidth]);

  // Today marker
  const today = new Date().toISOString().split("T")[0];
  const todayOffset = getDaysFromStart(today, study.startDate) * dayWidth;
  const isTodayVisible = todayOffset >= 0 && todayOffset <= totalWidth;

  // Collect all tasks
  const allTasks = study.phases.flatMap(p => p.tasks);
  const completedTasks = allTasks.filter(t => t.status === "completed").length;
  const inProgressTasks = allTasks.filter(t => t.status === "in_progress").length;
  const milestones = allTasks.filter(t => t.isMilestone);

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/analytics/visualizations">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Visualizations
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Study Timeline</h1>
            <p className="text-muted-foreground">
              Gantt chart view of clinical trial milestones and tasks
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setZoomLevel(Math.max(0.5, zoomLevel - 0.25))}>
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => setZoomLevel(Math.min(3, zoomLevel + 0.25))}>
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Study Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{study.name}</CardTitle>
              <CardDescription>
                {study.sponsor} | Protocol: {study.protocol}
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-lg px-4 py-2">
              {study.currentPhase}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-5">
            <div className="text-center p-3 rounded-lg bg-muted">
              <div className="text-2xl font-bold">{formatDate(study.startDate)}</div>
              <div className="text-xs text-muted-foreground">Study Start</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-muted">
              <div className="text-2xl font-bold">{formatDate(study.endDate)}</div>
              <div className="text-xs text-muted-foreground">Planned End</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-muted">
              <div className="text-2xl font-bold">
                {study.enrollmentCurrent}/{study.enrollmentTarget}
              </div>
              <div className="text-xs text-muted-foreground">Enrollment</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-green-50 dark:bg-green-950">
              <div className="text-2xl font-bold text-green-600">{completedTasks}</div>
              <div className="text-xs text-muted-foreground">Completed Tasks</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-blue-50 dark:bg-blue-950">
              <div className="text-2xl font-bold text-blue-600">{inProgressTasks}</div>
              <div className="text-xs text-muted-foreground">In Progress</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Legend */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 rounded" />
              <span className="text-sm">Completed</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-blue-500 rounded" />
              <span className="text-sm">In Progress</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-amber-500 rounded" />
              <span className="text-sm">Delayed</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-gray-300 dark:bg-gray-600 rounded" />
              <span className="text-sm">Not Started</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rotate-45 bg-gray-400 border border-white" />
              <span className="text-sm">Milestone</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-0.5 h-4 bg-red-500" />
              <span className="text-sm">Today</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Gantt Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Project Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="w-full">
            <div style={{ width: totalWidth + 300, minWidth: "100%" }}>
              {/* Month Headers */}
              <div className="flex border-b relative h-8" style={{ marginLeft: 250 }}>
                {months.map((month, i) => (
                  <div
                    key={i}
                    className="absolute text-xs text-muted-foreground border-l pl-1"
                    style={{ left: month.offset }}
                  >
                    {month.label}
                  </div>
                ))}
              </div>

              {/* Today Marker */}
              {isTodayVisible && (
                <div
                  className="absolute w-0.5 bg-red-500 z-20"
                  style={{
                    left: 250 + todayOffset,
                    top: 40,
                    height: study.phases.length * 200,
                  }}
                />
              )}

              {/* Phases and Tasks */}
              <div className="space-y-4 mt-4">
                {study.phases.map((phase) => (
                  <div key={phase.id} className="relative">
                    <div className="flex items-stretch">
                      {/* Phase Label */}
                      <div className="w-[250px] flex-shrink-0 pr-4">
                        <div className="font-medium">{phase.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {formatDate(phase.startDate)} - {formatDate(phase.endDate)}
                        </div>
                      </div>

                      {/* Tasks Row */}
                      <div className="flex-1 relative" style={{ height: (phase.tasks.length * 36) + 20 }}>
                        {/* Grid lines */}
                        {months.map((month, i) => (
                          <div
                            key={i}
                            className="absolute top-0 bottom-0 w-px bg-gray-200 dark:bg-gray-700"
                            style={{ left: month.offset }}
                          />
                        ))}

                        {/* Tasks */}
                        {phase.tasks.map((task, taskIndex) => (
                          <div
                            key={task.id}
                            className="absolute w-full"
                            style={{ top: taskIndex * 36 + 10, height: 36 }}
                          >
                            <GanttBar
                              task={task}
                              studyStart={study.startDate}
                              totalDays={totalDays}
                              dayWidth={dayWidth}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <ScrollBar orientation="horizontal" />
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Milestones Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Milestone className="h-5 w-5" />
            Key Milestones
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {milestones.map((milestone) => (
              <div
                key={milestone.id}
                className={`flex items-center gap-3 p-3 rounded-lg border ${getCategoryColor(milestone.category)}`}
              >
                {milestone.status === "completed" ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                ) : milestone.status === "in_progress" ? (
                  <PlayCircle className="h-5 w-5 text-blue-600" />
                ) : (
                  <Flag className="h-5 w-5 text-gray-500" />
                )}
                <div className="flex-1">
                  <div className="font-medium text-sm">{milestone.name}</div>
                  <div className="text-xs text-muted-foreground">{formatDate(milestone.startDate)}</div>
                </div>
                <Badge className={getStatusBadgeColor(milestone.status)}>
                  {milestone.status.replace("_", " ")}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
