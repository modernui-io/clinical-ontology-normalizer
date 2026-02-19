"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
import { Input } from "@/components/ui/input";
import {
  getPatients,
  Patient,
} from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { DEMO_PATIENTS } from "@/lib/demo-data";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";
import {
  Users,
  Network,
  ArrowRight,
  Activity,
  Pill,
  Stethoscope,
  Loader2,
  Search,
  ChevronLeft,
  ChevronRight,
  FileText,
  Heart,
} from "lucide-react";

const PAGE_SIZE = 20;

function formatPatientName(patient: Patient): string {
  if (patient.name && !patient.name.startsWith("Patient ")) {
    return patient.name;
  }
  // Make test IDs more readable
  const id = patient.name?.replace("Patient ", "") || patient.id;
  return id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\d{10,}/, (match) => "#" + match.slice(-4));
}

function getInitials(patient: Patient): string {
  const name = formatPatientName(patient);
  const words = name.split(" ").filter(Boolean);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

const AVATAR_COLORS = [
  "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300",
  "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
  "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
];

function getAvatarColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash << 5) - hash + id.charCodeAt(i);
    hash |= 0;
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export default function PatientsPage() {
  const { isDemo, isLoading: isAuthLoading } = useAuth();

  // Browse list state
  const [patients, setPatients] = useState<Patient[]>([]);
  const [totalPatients, setTotalPatients] = useState(0);
  const [isBrowseLoading, setIsBrowseLoading] = useState(true);
  const [browseError, setBrowseError] = useState<string | null>(null);
  const [dataMode, setDataMode] = useState<"live" | "simulation">("live");

  // Search / filter / pagination
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);

  // Load patient list on mount
  useEffect(() => {
    if (isAuthLoading) return;
    if (isDemo) {
      setPatients(DEMO_PATIENTS);
      setTotalPatients(DEMO_PATIENTS.length);
      setDataMode("simulation");
      setIsBrowseLoading(false);
      return;
    }
    let cancelled = false;
    async function loadPatients() {
      setIsBrowseLoading(true);
      setBrowseError(null);
      try {
        const resp = await getPatients({ page: 1, page_size: 200 });
        if (!cancelled) {
          setPatients(resp.patients);
          setTotalPatients(resp.total);
        }
      } catch (err) {
        console.error("Failed to load patients:", err);
        if (!cancelled) {
          setPatients(DEMO_PATIENTS);
          setTotalPatients(DEMO_PATIENTS.length);
          setDataMode("simulation");
        }
      } finally {
        if (!cancelled) {
          setIsBrowseLoading(false);
        }
      }
    }
    loadPatients();
    return () => { cancelled = true; };
  }, [isAuthLoading, isDemo]);

  // Client-side filter
  const filteredPatients = useMemo(() => {
    if (!searchQuery.trim()) return patients;
    const q = searchQuery.toLowerCase();
    return patients.filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        (p.name && p.name.toLowerCase().includes(q)) ||
        (p.external_id && p.external_id.toLowerCase().includes(q)) ||
        (p.conditions && p.conditions.some((c) => c.toLowerCase().includes(q))) ||
        (p.medications && p.medications.some((m) => m.toLowerCase().includes(q)))
    );
  }, [patients, searchQuery]);

  // Pagination
  const totalPages = Math.ceil(filteredPatients.length / PAGE_SIZE);
  const paginatedPatients = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredPatients.slice(start, start + PAGE_SIZE);
  }, [filteredPatients, currentPage]);

  // Reset page when search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  // Summary stats
  const stats = useMemo(() => {
    const withConditions = patients.filter((p) => p.conditions && p.conditions.length > 0).length;
    const withMedications = patients.filter((p) => p.medications && p.medications.length > 0).length;
    const totalFacts = patients.reduce((sum, p) => sum + (p.fact_count || 0), 0);
    const totalNodes = patients.reduce((sum, p) => sum + (p.node_count || 0), 0);
    return { withConditions, withMedications, totalFacts, totalNodes };
  }, [patients]);

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Patients</h1>
        <p className="text-muted-foreground">
          Browse patient records, clinical facts, and knowledge graphs
        </p>
      </div>

      {dataMode === "simulation" && (
        <DataSourceModeBanner
          mode={dataMode}
          title="Patients data source"
          description="Backend API is unavailable. Patient list shows demonstration patient records."
          backendEndpoints={["/api/v1/patients"]}
        />
      )}

      {/* Stats Cards */}
      {!isBrowseLoading && patients.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Patients</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalPatients}</div>
              <p className="text-xs text-muted-foreground">in the system</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">With Conditions</CardTitle>
              <Heart className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.withConditions}</div>
              <p className="text-xs text-muted-foreground">
                {totalPatients > 0 ? Math.round((stats.withConditions / totalPatients) * 100) : 0}% of patients
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Clinical Facts</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalFacts.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">
                across all patients
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">KG Nodes</CardTitle>
              <Network className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalNodes.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">
                in knowledge graphs
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Patient List */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Stethoscope className="h-5 w-5" />
                All Patients
                {filteredPatients.length > 0 && (
                  <Badge variant="secondary" className="ml-1">
                    {filteredPatients.length}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Browse all patients with clinical data in the system
              </CardDescription>
            </div>
            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Filter patients..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isBrowseLoading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <span className="ml-3 text-muted-foreground">
                Loading patients...
              </span>
            </div>
          )}

          {browseError && (
            <div className="text-center py-12 text-muted-foreground">
              <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-sm">{browseError}</p>
            </div>
          )}

          {!isBrowseLoading && !browseError && patients.length === 0 && (
            <div className="text-center py-16 text-muted-foreground">
              <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">No patients yet</p>
              <p className="text-sm mt-1">
                Ingest clinical documents to populate patient records
              </p>
            </div>
          )}

          {!isBrowseLoading && !browseError && filteredPatients.length === 0 && patients.length > 0 && (
            <div className="text-center py-12 text-muted-foreground">
              <Search className="h-10 w-10 mx-auto mb-3 opacity-50" />
              <p className="font-medium">No matching patients</p>
              <p className="text-sm mt-1">Try adjusting your search terms</p>
            </div>
          )}

          {!isBrowseLoading && !browseError && paginatedPatients.length > 0 && (
            <>
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="w-[280px]">Patient</TableHead>
                      <TableHead>Conditions</TableHead>
                      <TableHead>Medications</TableHead>
                      <TableHead className="text-right w-[80px]">Facts</TableHead>
                      <TableHead className="text-right w-[80px]">Nodes</TableHead>
                      <TableHead className="w-[100px]"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedPatients.map((patient) => (
                      <TableRow key={patient.id} className="group">
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <div
                              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${getAvatarColor(patient.id)}`}
                            >
                              {getInitials(patient)}
                            </div>
                            <div className="min-w-0">
                              <Link
                                href={`/patients/${patient.id}/graph`}
                                className="font-medium text-foreground hover:text-primary hover:underline underline-offset-2 transition-colors truncate block"
                              >
                                {formatPatientName(patient)}
                              </Link>
                              <div className="flex items-center gap-1.5 mt-0.5">
                                <span className="font-mono text-[11px] text-muted-foreground truncate">
                                  {patient.id}
                                </span>
                                {patient.gender && (
                                  <>
                                    <span className="text-muted-foreground/40">|</span>
                                    <span className="text-[11px] text-muted-foreground capitalize">
                                      {patient.gender}
                                    </span>
                                  </>
                                )}
                                {patient.birth_date && (
                                  <>
                                    <span className="text-muted-foreground/40">|</span>
                                    <span className="text-[11px] text-muted-foreground">
                                      {patient.birth_date}
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          {patient.conditions && patient.conditions.length > 0 ? (
                            <div className="flex flex-wrap gap-1 max-w-[240px]">
                              {patient.conditions.slice(0, 2).map((c, i) => (
                                <Badge
                                  key={i}
                                  variant="outline"
                                  className="text-[11px] px-2 py-0.5 font-normal"
                                >
                                  {c}
                                </Badge>
                              ))}
                              {patient.conditions.length > 2 && (
                                <Badge
                                  variant="secondary"
                                  className="text-[11px] px-2 py-0.5 font-normal"
                                >
                                  +{patient.conditions.length - 2}
                                </Badge>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground/50">
                              No conditions recorded
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          {patient.medications && patient.medications.length > 0 ? (
                            <div className="flex flex-wrap gap-1 max-w-[200px]">
                              {patient.medications.slice(0, 2).map((m, i) => (
                                <Badge
                                  key={i}
                                  variant="secondary"
                                  className="text-[11px] px-2 py-0.5 font-normal"
                                >
                                  <Pill className="h-2.5 w-2.5 mr-1 opacity-60" />
                                  {m}
                                </Badge>
                              ))}
                              {patient.medications.length > 2 && (
                                <Badge
                                  variant="secondary"
                                  className="text-[11px] px-2 py-0.5 font-normal"
                                >
                                  +{patient.medications.length - 2}
                                </Badge>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground/50">
                              No medications recorded
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <span className="font-mono text-sm tabular-nums">
                            {patient.fact_count || 0}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <span className="font-mono text-sm tabular-nums">
                            {patient.node_count || 0}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Link href={`/patients/${patient.id}/graph`}>
                              <Button variant="ghost" size="sm" className="h-8 px-2">
                                <Network className="h-3.5 w-3.5" />
                              </Button>
                            </Link>
                            <Link href={`/patients/${patient.id}/facts`}>
                              <Button variant="ghost" size="sm" className="h-8 px-2">
                                <FileText className="h-3.5 w-3.5" />
                              </Button>
                            </Link>
                            <Link href={`/patients/${patient.id}/graph`}>
                              <Button variant="ghost" size="sm" className="h-8 gap-1 px-2">
                                <ArrowRight className="h-3.5 w-3.5" />
                              </Button>
                            </Link>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4">
                  <p className="text-sm text-muted-foreground">
                    Showing {((currentPage - 1) * PAGE_SIZE) + 1}–{Math.min(currentPage * PAGE_SIZE, filteredPatients.length)} of {filteredPatients.length} patients
                  </p>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage === 1}
                      onClick={() => setCurrentPage((p) => p - 1)}
                      className="h-8 w-8 p-0"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                      let pageNum: number;
                      if (totalPages <= 5) {
                        pageNum = i + 1;
                      } else if (currentPage <= 3) {
                        pageNum = i + 1;
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i;
                      } else {
                        pageNum = currentPage - 2 + i;
                      }
                      return (
                        <Button
                          key={pageNum}
                          variant={currentPage === pageNum ? "default" : "outline"}
                          size="sm"
                          onClick={() => setCurrentPage(pageNum)}
                          className="h-8 w-8 p-0"
                        >
                          {pageNum}
                        </Button>
                      );
                    })}
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage === totalPages}
                      onClick={() => setCurrentPage((p) => p + 1)}
                      className="h-8 w-8 p-0"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
