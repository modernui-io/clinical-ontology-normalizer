"use client";

import { useState, useCallback, useEffect } from "react";
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
import { SearchWithDebounce } from "@/components/SearchWithDebounce";
import { SkeletonCard } from "@/components/ui/skeleton";
import {
  getPatientGraph,
  getPatients,
  PatientGraph,
  Patient,
} from "@/lib/api";
import {
  Users,
  Network,
  ArrowRight,
  Activity,
  Pill,
  Stethoscope,
  Loader2,
} from "lucide-react";

export default function PatientsPage() {
  const [patientId, setPatientId] = useState("");
  const [graph, setGraph] = useState<PatientGraph | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // Browse list state
  const [patients, setPatients] = useState<Patient[]>([]);
  const [totalPatients, setTotalPatients] = useState(0);
  const [isBrowseLoading, setIsBrowseLoading] = useState(true);
  const [browseError, setBrowseError] = useState<string | null>(null);

  // Load patient list on mount
  useEffect(() => {
    let cancelled = false;
    async function loadPatients() {
      setIsBrowseLoading(true);
      setBrowseError(null);
      try {
        const resp = await getPatients({ page: 1, page_size: 100 });
        if (!cancelled) {
          setPatients(resp.patients);
          setTotalPatients(resp.total);
        }
      } catch (err) {
        console.error("Failed to load patients:", err);
        if (!cancelled) {
          setBrowseError("Failed to load patient list. Is the backend running?");
        }
      } finally {
        if (!cancelled) {
          setIsBrowseLoading(false);
        }
      }
    }
    loadPatients();
    return () => { cancelled = true; };
  }, []);

  const handleSearch = useCallback(async (searchValue: string) => {
    if (!searchValue.trim()) {
      setGraph(null);
      setHasSearched(false);
      return;
    }

    setIsLoading(true);
    setHasSearched(true);

    try {
      const patientGraph = await getPatientGraph(searchValue.trim());
      setGraph(patientGraph);
    } catch (error) {
      console.error("Failed to fetch patient graph:", error);
      toast.error("Patient not found or backend unavailable");
      setGraph(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleClear = useCallback(() => {
    setGraph(null);
    setHasSearched(false);
  }, []);

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Patients</h1>
        <p className="text-muted-foreground">
          View and manage patient records and knowledge graphs
        </p>
      </div>

      <div className="space-y-6">
        {/* Search Card */}
        <div className="mx-auto max-w-2xl">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Find Patient
              </CardTitle>
              <CardDescription>
                Search for a patient by ID to view their knowledge graph
              </CardDescription>
            </CardHeader>
            <CardContent>
              <SearchWithDebounce
                placeholder="Search by Patient ID (e.g., P001)..."
                value={patientId}
                onChange={setPatientId}
                onSearch={handleSearch}
                onClear={handleClear}
                isLoading={isLoading}
                debounceMs={500}
                size="lg"
              />
            </CardContent>
          </Card>
        </div>

        {/* Loading State for Search */}
        {isLoading && (
          <div className="mx-auto max-w-2xl">
            <SkeletonCard showHeader showFooter contentLines={2} />
          </div>
        )}

        {/* Search Results */}
        {!isLoading && graph && (
          <div className="mx-auto max-w-2xl">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Network className="h-5 w-5 text-primary" />
                  Patient {graph.patient_id}
                </CardTitle>
                <CardDescription>
                  Knowledge graph containing {graph.node_count} nodes and{" "}
                  {graph.edge_count} edges
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20 transition-colors">
                    <div className="text-2xl font-bold text-blue-800 dark:text-blue-200">
                      {graph.node_count}
                    </div>
                    <div className="text-sm text-blue-600 dark:text-blue-300">
                      Total Nodes
                    </div>
                  </div>
                  <div className="rounded-lg bg-green-50 p-4 dark:bg-green-900/20 transition-colors">
                    <div className="text-2xl font-bold text-green-800 dark:text-green-200">
                      {graph.edge_count}
                    </div>
                    <div className="text-sm text-green-600 dark:text-green-300">
                      Total Edges
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Link
                    href={`/patients/${graph.patient_id}/graph`}
                    className="flex-1"
                  >
                    <Button className="w-full gap-2">
                      View Knowledge Graph
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Link href={`/patients/${graph.patient_id}/timeline`}>
                    <Button variant="outline">Timeline</Button>
                  </Link>
                  <Link href={`/patients/${graph.patient_id}/facts`}>
                    <Button variant="outline">Facts</Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* No Results from Search */}
        {!isLoading && hasSearched && !graph && (
          <div className="mx-auto max-w-2xl">
            <Card>
              <CardContent className="py-8">
                <div className="text-center text-muted-foreground">
                  <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">No patient found</p>
                  <p className="text-sm">
                    Try searching with a different patient ID
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Browse All Patients */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Stethoscope className="h-5 w-5" />
              All Patients
              {totalPatients > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {totalPatients}
                </Badge>
              )}
            </CardTitle>
            <CardDescription>
              Browse all patients with clinical data in the system
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isBrowseLoading && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <span className="ml-3 text-muted-foreground">
                  Loading patients...
                </span>
              </div>
            )}

            {browseError && (
              <div className="text-center py-8 text-muted-foreground">
                <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-sm">{browseError}</p>
              </div>
            )}

            {!isBrowseLoading && !browseError && patients.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-lg font-medium">No patients yet</p>
                <p className="text-sm">
                  Ingest clinical documents to populate patient records
                </p>
              </div>
            )}

            {!isBrowseLoading && !browseError && patients.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient</TableHead>
                    <TableHead>ID / MRN</TableHead>
                    <TableHead>Demographics</TableHead>
                    <TableHead>Conditions</TableHead>
                    <TableHead>Medications</TableHead>
                    <TableHead className="text-right">Facts</TableHead>
                    <TableHead className="text-right">KG Nodes</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {patients.map((patient) => (
                    <TableRow key={patient.id}>
                      <TableCell className="font-medium">
                        <Link
                          href={`/patients/${patient.id}/graph`}
                          className="text-primary hover:underline"
                        >
                          {patient.name || patient.id}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          <div className="font-mono text-xs text-muted-foreground">
                            {patient.id}
                          </div>
                          {patient.external_id && (
                            <div className="text-xs text-muted-foreground">
                              {patient.external_id}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm text-muted-foreground">
                          {patient.gender && (
                            <span className="capitalize">
                              {patient.gender}
                            </span>
                          )}
                          {patient.gender && patient.birth_date && " · "}
                          {patient.birth_date && (
                            <span>{patient.birth_date}</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1 max-w-[220px]">
                          {patient.conditions &&
                          patient.conditions.length > 0 ? (
                            patient.conditions.slice(0, 3).map((c, i) => (
                              <Badge
                                key={i}
                                variant="outline"
                                className="text-[10px] px-1.5 py-0"
                              >
                                {c}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              --
                            </span>
                          )}
                          {patient.conditions &&
                            patient.conditions.length > 3 && (
                              <span className="text-xs text-muted-foreground">
                                +{patient.conditions.length - 3}
                              </span>
                            )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1 max-w-[180px]">
                          {patient.medications &&
                          patient.medications.length > 0 ? (
                            patient.medications.slice(0, 2).map((m, i) => (
                              <Badge
                                key={i}
                                variant="secondary"
                                className="text-[10px] px-1.5 py-0"
                              >
                                <Pill className="h-2.5 w-2.5 mr-0.5" />
                                {m}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              --
                            </span>
                          )}
                          {patient.medications &&
                            patient.medications.length > 2 && (
                              <span className="text-xs text-muted-foreground">
                                +{patient.medications.length - 2}
                              </span>
                            )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Activity className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="font-mono text-sm">
                            {patient.fact_count}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Network className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="font-mono text-sm">
                            {patient.node_count}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Link href={`/patients/${patient.id}/graph`}>
                          <Button variant="ghost" size="sm" className="gap-1">
                            View
                            <ArrowRight className="h-3.5 w-3.5" />
                          </Button>
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
