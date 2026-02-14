"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Search,
  RefreshCw,
  AlertTriangle,
  AlertCircle,
  ShieldAlert,
  FileWarning,
  Loader2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AdverseEvent {
  id: string;
  trial_id: string;
  patient_id: string;
  site_id: string;
  event_term: string;
  preferred_term: string;
  category: string;
  severity: string;
  relatedness: string;
  serious: boolean;
  expected: boolean;
  status: string;
  onset_date: string;
  resolution_date: string | null;
  reported_date: string;
  reporter: string;
  description: string;
  action_taken: string;
  outcome: string;
  requires_expedited_reporting: boolean;
}

interface AdverseEventsResponse {
  items: AdverseEvent[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Badge color maps
// ---------------------------------------------------------------------------

const severityColors: Record<string, string> = {
  MILD: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  MODERATE: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  SEVERE: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
  LIFE_THREATENING: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
};

const statusColors: Record<string, string> = {
  REPORTED: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  UNDER_INVESTIGATION: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  RESOLVED: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  FOLLOW_UP: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdverseEventsPage() {
  const [events, setEvents] = useState<AdverseEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/adverse-events/events");
      if (!res.ok) throw new Error(`Failed to fetch adverse events (${res.status})`);
      const data: AdverseEventsResponse = await res.json();
      setEvents(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unknown error occurred");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Derived stats
  const totalCount = events.length;
  const seriousCount = events.filter((e) => e.serious).length;
  const openCount = events.filter((e) => e.status !== "RESOLVED").length;
  const expeditedCount = events.filter((e) => e.requires_expedited_reporting).length;

  // Filtered list
  const filtered = searchQuery
    ? events.filter((e) =>
        e.event_term.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : events;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-muted-foreground">Loading adverse events...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <AlertCircle className="h-10 w-10 text-red-500" />
        <p className="text-red-600 font-medium">{error}</p>
        <Button variant="outline" size="sm" onClick={fetchEvents}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Adverse Events</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track and manage adverse event reports across trials
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchEvents}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total AEs</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Serious AEs</CardTitle>
            <ShieldAlert className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{seriousCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Open Cases</CardTitle>
            <AlertCircle className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{openCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Expedited Reporting</CardTitle>
            <FileWarning className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">{expeditedCount}</div>
          </CardContent>
        </Card>
      </div>

      {/* Search Filter */}
      <Card>
        <CardContent className="pt-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by event term..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </CardContent>
      </Card>

      {/* Events Table */}
      <Card>
        <CardHeader>
          <CardTitle>Events</CardTitle>
          <CardDescription>
            Showing {filtered.length} of {totalCount} adverse events
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              No adverse events found
            </div>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Event Term</TableHead>
                    <TableHead>Patient</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Serious</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Relatedness</TableHead>
                    <TableHead>Onset Date</TableHead>
                    <TableHead>Reporter</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell className="font-mono text-sm">
                        {event.id}
                      </TableCell>
                      <TableCell className="font-medium">
                        {event.event_term}
                      </TableCell>
                      <TableCell>{event.patient_id}</TableCell>
                      <TableCell>
                        <Badge className={severityColors[event.severity] || ""}>
                          {event.severity.replace("_", " ")}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          className={
                            event.serious
                              ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
                              : "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300"
                          }
                        >
                          {event.serious ? "Yes" : "No"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusColors[event.status] || ""}>
                          {event.status.replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {event.relatedness.replace(/_/g, " ")}
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(event.onset_date).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-sm">
                        {event.reporter}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
