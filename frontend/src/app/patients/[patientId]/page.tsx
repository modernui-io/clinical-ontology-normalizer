"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  FileText,
  Network,
  ClipboardList,
  Clock,
  User,
  Activity,
  Pill,
  Heart,
  ArrowLeft,
  Loader2,
} from "lucide-react";
import { Patient, ClinicalFact, getPatient, getPatientFacts, getPatientGraph, PatientGraph } from "@/lib/api";

export default function PatientDetailPage() {
  const params = useParams();
  const patientId = params.patientId as string;

  const [patient, setPatient] = useState<Patient | null>(null);
  const [facts, setFacts] = useState<ClinicalFact[]>([]);
  const [graph, setGraph] = useState<PatientGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [p, f, g] = await Promise.allSettled([
          getPatient(patientId),
          getPatientFacts(patientId, { limit: 200 }),
          getPatientGraph(patientId),
        ]);
        if (p.status === "fulfilled") setPatient(p.value);
        if (f.status === "fulfilled") setFacts(f.value);
        if (g.status === "fulfilled") setGraph(g.value);
        if (p.status === "rejected" && f.status === "rejected") {
          setError("Could not load patient data from the API.");
        }
      } catch {
        setError("Failed to load patient data.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [patientId]);

  // Derive stats from facts
  const conditions = facts.filter((f) => f.domain === "condition" && f.assertion !== "absent");
  const medications = facts.filter((f) => f.domain === "drug");
  const measurements = facts.filter((f) => f.domain === "measurement");
  const procedures = facts.filter((f) => f.domain === "procedure");

  const displayName = patient?.name || patientId;
  const gender = patient?.gender || "Unknown";
  const birthDate = patient?.birth_date || "Unknown";

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/patients" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                <ArrowLeft className="h-4 w-4 inline mr-1" />
                Patients
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                {displayName}
              </h1>
              {patient && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>{gender}</span>
                  {birthDate !== "Unknown" && (
                    <>
                      <span className="text-zinc-300">|</span>
                      <span>DOB: {birthDate}</span>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-6">
        {error && (
          <Card className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30">
            <CardContent className="py-4">
              <p className="text-sm text-amber-700 dark:text-amber-300">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Navigation cards to sub-pages */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link href={`/patients/${patientId}/facts`}>
            <Card className="hover:border-blue-500 hover:shadow-md transition-all cursor-pointer h-full">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <ClipboardList className="h-5 w-5 text-blue-600" />
                  Clinical Facts
                </CardTitle>
                <CardDescription>Normalized clinical data</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{facts.length}</p>
                <p className="text-xs text-muted-foreground mt-1">across all domains</p>
              </CardContent>
            </Card>
          </Link>

          <Link href={`/patients/${patientId}/graph`}>
            <Card className="hover:border-purple-500 hover:shadow-md transition-all cursor-pointer h-full">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Network className="h-5 w-5 text-purple-600" />
                  Knowledge Graph
                </CardTitle>
                <CardDescription>Interactive graph visualization</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{graph?.nodes?.length ?? patient?.node_count ?? 0}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  nodes, {graph?.edges?.length ?? 0} edges
                </p>
              </CardContent>
            </Card>
          </Link>

          <Link href={`/patients/${patientId}/timeline`}>
            <Card className="hover:border-green-500 hover:shadow-md transition-all cursor-pointer h-full">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="h-5 w-5 text-green-600" />
                  Timeline
                </CardTitle>
                <CardDescription>Chronological clinical events</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{patient?.document_count ?? 0}</p>
                <p className="text-xs text-muted-foreground mt-1">source documents</p>
              </CardContent>
            </Card>
          </Link>

          <Link href={`/patients/${patientId}/summary`}>
            <Card className="hover:border-amber-500 hover:shadow-md transition-all cursor-pointer h-full">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-5 w-5 text-amber-600" />
                  AI Summary
                </CardTitle>
                <CardDescription>LLM-generated patient summary</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Generate a clinical summary from all extracted facts
                </p>
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* Clinical overview */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Conditions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Heart className="h-4 w-4 text-red-500" />
                Conditions ({conditions.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {conditions.length === 0 ? (
                <p className="text-sm text-muted-foreground">No conditions extracted yet</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {conditions.slice(0, 20).map((f, i) => (
                    <Badge key={i} variant="secondary" className="bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300">
                      {f.concept_name || f.text || "Unknown"}
                    </Badge>
                  ))}
                  {conditions.length > 20 && (
                    <Badge variant="outline">+{conditions.length - 20} more</Badge>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Medications */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Pill className="h-4 w-4 text-blue-500" />
                Medications ({medications.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {medications.length === 0 ? (
                <p className="text-sm text-muted-foreground">No medications extracted yet</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {medications.slice(0, 20).map((f, i) => (
                    <Badge key={i} variant="secondary" className="bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
                      {f.concept_name || f.text || "Unknown"}
                    </Badge>
                  ))}
                  {medications.length > 20 && (
                    <Badge variant="outline">+{medications.length - 20} more</Badge>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Measurements */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Activity className="h-4 w-4 text-green-500" />
                Measurements ({measurements.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {measurements.length === 0 ? (
                <p className="text-sm text-muted-foreground">No measurements extracted yet</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {measurements.slice(0, 20).map((f, i) => (
                    <Badge key={i} variant="secondary" className="bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300">
                      {f.concept_name || f.text || "Unknown"}
                      {f.value && `: ${f.value}${f.unit ? ` ${f.unit}` : ""}`}
                    </Badge>
                  ))}
                  {measurements.length > 20 && (
                    <Badge variant="outline">+{measurements.length - 20} more</Badge>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Procedures */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <User className="h-4 w-4 text-orange-500" />
                Procedures ({procedures.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {procedures.length === 0 ? (
                <p className="text-sm text-muted-foreground">No procedures extracted yet</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {procedures.slice(0, 20).map((f, i) => (
                    <Badge key={i} variant="secondary" className="bg-orange-50 text-orange-700 dark:bg-orange-900/20 dark:text-orange-300">
                      {f.concept_name || f.text || "Unknown"}
                    </Badge>
                  ))}
                  {procedures.length > 20 && (
                    <Badge variant="outline">+{procedures.length - 20} more</Badge>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
