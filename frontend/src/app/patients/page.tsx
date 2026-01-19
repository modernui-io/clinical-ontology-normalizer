"use client";

import { useState, useCallback } from "react";
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
import { SearchWithDebounce } from "@/components/SearchWithDebounce";
import { SkeletonCard } from "@/components/ui/skeleton";
import { getPatientGraph, PatientGraph } from "@/lib/api";
import { Users, Network, ArrowRight } from "lucide-react";

export default function PatientsPage() {
  const [patientId, setPatientId] = useState("");
  const [graph, setGraph] = useState<PatientGraph | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

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

      <div className="mx-auto max-w-2xl space-y-6">
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

        {/* Loading State */}
        {isLoading && (
          <SkeletonCard showHeader showFooter contentLines={2} />
        )}

        {/* Results */}
        {!isLoading && graph && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Network className="h-5 w-5 text-primary" />
                Patient {graph.patient_id}
              </CardTitle>
              <CardDescription>
                Knowledge graph containing {graph.node_count} nodes and {graph.edge_count} edges
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
                <Link href={`/patients/${graph.patient_id}/graph`} className="flex-1">
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
        )}

        {/* No Results */}
        {!isLoading && hasSearched && !graph && (
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
        )}
      </div>
    </div>
  );
}
